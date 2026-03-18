"""
AI Data Analysis Tool — Backend
FastAPI + APScheduler + Multi-LLM support (OpenAI / Anthropic / Google Gemini)
Supports uploading MULTIPLE files per session (e.g. all Search Console exports).
"""

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import List

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import anthropic
import openai
import io
import contextlib
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, File, Header, HTTPException, UploadFile, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
TMP_DIR = Path("/tmp/ai_data_analysis")
TMP_DIR.mkdir(parents=True, exist_ok=True)

SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
MAX_FILE_BYTES      = 50 * 1024 * 1024  # 50 MB per file
SAMPLE_ROWS         = 5

# Sessions: session_id → {files: [{var_name, filename, path, schema}], last_access}
SESSIONS: dict[str, dict] = {}


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(title="AI Data Analysis Tool", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ─────────────────────────────────────────────
# API Router (Defined FIRST)
# ─────────────────────────────────────────────
api_router = APIRouter(prefix="/api")

@api_router.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(SESSIONS)}

@api_router.get("/test")
async def test_route():
    return {"message": "API router is active", "version": "1.2.2-STABLE"}


# ─────────────────────────────────────────────
# APScheduler — cleanup stale sessions
# ─────────────────────────────────────────────
def cleanup_stale_sessions():
    now = time.time()
    expired = [
        sid for sid, meta in SESSIONS.items()
        if now - meta["last_access"] > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        for f in SESSIONS[sid].get("files", []):
            p = Path(f.get("path", ""))
            if p.exists():
                os.remove(p)
        del SESSIONS[sid]
    if expired:
        print(f"[Scheduler] Cleaned up {len(expired)} expired session(s).")


scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_stale_sessions, "interval", minutes=5, id="cleanup")
scheduler.start()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _to_var_name(filename: str) -> str:
    """Convert filename to a safe Python variable name: 'Search appearance.csv' → 'df_search_appearance'"""
    stem = Path(filename).stem                  # drop extension
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", stem) # replace non-alnum with _
    slug = slug.strip("_").lower()
    return f"df_{slug}"


def _load_dataframe(path: str, original_filename: str) -> pd.DataFrame:
    ext = Path(original_filename).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(path, engine="openpyxl")
    raise ValueError(f"Unsupported file type: {ext}")


def _build_schema(df: pd.DataFrame) -> dict:
    columns = [{"name": col, "dtype": str(df[col].dtype)} for col in df.columns]
    sample  = json.loads(df.head(SAMPLE_ROWS).to_json(orient="records", date_format="iso"))
    return {"columns": columns, "sample": sample, "row_count": len(df)}


def _touch_session(session_id: str):
    if session_id in SESSIONS:
        SESSIONS[session_id]["last_access"] = time.time()


def _get_session(session_id: str) -> dict:
    if session_id not in SESSIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}. Please re-upload your files."
        )
    _touch_session(session_id)
    return SESSIONS[session_id]


def _schema_prompt_block(meta: dict) -> str:
    """
    Build the LLM context block describing ALL loaded DataFrames.
    Each DataFrame is accessible as df_<slug> in the exec sandbox.
    """
    parts = []
    for f in meta["files"]:
        var   = f["var_name"]
        fname = f["filename"]
        cols  = f["schema"]["columns"]
        col_str    = ", ".join(f"{c['name']} ({c['dtype']})" for c in cols)
        sample_str = json.dumps(f["schema"]["sample"], ensure_ascii=False)
        parts.append(
            f"### `{var}` — {fname} ({f['schema']['row_count']} rows)\n"
            f"Columns: {col_str}\n"
            f"Sample rows:\n{sample_str}"
        )
    return "\n\n".join(parts)


def _load_all_dataframes(meta: dict) -> dict[str, pd.DataFrame]:
    """Return a dict {var_name: DataFrame} for all files in the session."""
    dfs = {}
    for f in meta["files"]:
        dfs[f["var_name"]] = _load_dataframe(f["path"], f["filename"])
    return dfs


# ─────────────────────────────────────────────
# LLM Router
# ─────────────────────────────────────────────
def _call_llm(api_key: str, messages: list[dict], system_prompt: str = "") -> str:
    """
    Auto-detect provider from API key prefix:
      sk-ant-*  → Anthropic (Claude 3.5 Sonnet)
      AIza*     → Google Gemini (Gemini 1.5 Flash)
      sk-*      → OpenAI (GPT-4o Mini)
    """
    if api_key.startswith("sk-ant-"):
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=system_prompt or "You are a helpful data analysis assistant.",
            messages=messages,
        )
        return response.content[0].text

    elif api_key.startswith("AIza"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model      = genai.GenerativeModel("gemini-1.5-flash")
        full_prompt = (system_prompt + "\n\n" if system_prompt else "") + "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        )
        return model.generate_content(full_prompt).text

    else:
        client = openai.OpenAI(api_key=api_key)
        system_msg = {"role": "system", "content": system_prompt or "You are a helpful data analysis assistant."}
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[system_msg] + messages,
            max_tokens=2048,
        )
        return response.choices[0].message.content


# ─────────────────────────────────────────────
# Safe exec sandbox
# ─────────────────────────────────────────────
SAFE_BUILTINS = {
    "__builtins__": {
        "len": len, "range": range, "enumerate": enumerate,
        "zip": zip, "list": list, "dict": dict, "str": str,
        "int": int, "float": float, "bool": bool, "print": print,
        "sorted": sorted, "reversed": reversed, "min": min, "max": max,
        "sum": sum, "abs": abs, "round": round, "isinstance": isinstance,
        "hasattr": hasattr, "getattr": getattr,
        "set": set, "tuple": tuple,
    },
}

import datetime as dt_mod
SAFE_LIBS = {
    "pd": pd, "px": px, "go": go, 
    "np": np, 
    "datetime": dt_mod.datetime, 
    "timedelta": dt_mod.timedelta
}


def _safe_exec_chart(code: str, dfs: dict[str, pd.DataFrame]) -> dict:
    """
    Execute LLM-generated Plotly code in a restricted sandbox.
    All DataFrames are available as their var_name (e.g. df_queries, df_pages).
    Returns Plotly JSON dict.
    """
    local_ns = {**dfs}
    # Also expose 'df' as the first/primary DataFrame for convenience
    if dfs:
        local_ns["df"] = next(iter(dfs.values()))

    exec(code, {**SAFE_BUILTINS, **SAFE_LIBS}, local_ns)  # noqa: S102

    fig = local_ns.get("fig")
    if fig is None:
        for v in local_ns.values():
            if isinstance(v, go.Figure):
                fig = v
                break
    if fig is None:
        raise ValueError("The generated code did not produce a Plotly figure named 'fig'.")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1E293B",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0"),
    )
    return json.loads(pio.to_json(fig))


def _safe_exec_data_code(code: str, dfs: dict[str, pd.DataFrame]) -> str:
    """Execute LLM-generated analysis Python code and return captured stdout."""
    local_ns = {**dfs}
    if dfs:
        local_ns["df"] = next(iter(dfs.values()))
    
    f = io.StringIO()
    try:
        with contextlib.redirect_stdout(f):
            exec(code, {**SAFE_BUILTINS, **SAFE_LIBS}, local_ns)  # noqa: S102
        return f.getvalue() or "No output (did you forget to use print?)"
    except Exception as e:
        return f"Execution error: {e}"


# ─────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────
class ChartRequest(BaseModel):
    file_id: str
    prompt: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    file_id: str
    messages: list[ChatMessage]


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@api_router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload one or more CSV / XLSX files in a single request.
    Returns: session_id + per-file schemas and variable names.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    session_id  = str(uuid.uuid4())
    file_metas  = []
    errors      = []

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in (".csv", ".xlsx", ".xls"):
            errors.append(f"{file.filename}: unsupported type (only CSV/XLSX).")
            continue

        content = await file.read()
        if len(content) > MAX_FILE_BYTES:
            errors.append(f"{file.filename}: exceeds 50 MB limit.")
            continue

        file_uuid = str(uuid.uuid4())
        dest      = TMP_DIR / f"{file_uuid}{ext}"
        dest.write_bytes(content)

        try:
            df     = _load_dataframe(str(dest), file.filename)
            schema = _build_schema(df)
        except Exception as e:
            dest.unlink(missing_ok=True)
            errors.append(f"{file.filename}: parse error — {e}")
            continue

        var_name = _to_var_name(file.filename)
        file_metas.append({
            "var_name": var_name,
            "filename": file.filename,
            "path":     str(dest),
            "schema":   schema,
        })

    if not file_metas:
        raise HTTPException(status_code=422, detail="No files could be processed. " + " | ".join(errors))

    SESSIONS[session_id] = {
        "files":       file_metas,
        "last_access": time.time(),
    }

    return {
        "session_id": session_id,
        "files": [
            {
                "var_name": f["var_name"],
                "filename": f["filename"],
                **f["schema"],
            }
            for f in file_metas
        ],
        "warnings": errors or None,
    }


@api_router.post("/chart")
async def generate_chart(body: ChartRequest, x_api_key: str = Header(...)):
    """
    Generate a Plotly chart from a natural-language prompt.
    All DataFrames in the session are available in the exec sandbox.
    """
    meta = _get_session(body.file_id)
    dfs  = _load_all_dataframes(meta)

    # Build variable name list for the prompt
    df_list = ", ".join(f"`{f['var_name']}` ({f['filename']})" for f in meta["files"])

    system_prompt = (
        "You are an expert data visualization engineer.\n"
        "You have access to multiple pandas DataFrames. Generate ONLY executable Python code "
        "using Plotly Express (px) or Plotly Graph Objects (go) to create a chart.\n"
        "Rules:\n"
        "1. Assign the final figure to a variable named `fig`.\n"
        "2. Do NOT import any libraries — pd, px, go, and all DataFrames are already available.\n"
        f"3. Available DataFrames: {df_list}\n"
        "4. Do NOT include explanations, markdown fences, or comments.\n"
        "5. Output ONLY the raw Python code.\n"
        "6. Use descriptive titles and axis labels.\n"
    )

    schema_block  = _schema_prompt_block(meta)
    user_message  = f"{schema_block}\n\nUser request: {body.prompt}"

    try:
        raw_code = _call_llm(
            api_key=x_api_key,
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM API error: {e}")

    # Strip markdown fences
    code = raw_code.strip()
    if code.startswith("```"):
        code = "\n".join(l for l in code.splitlines() if not l.startswith("```")).strip()

    try:
        chart_json = _safe_exec_chart(code, dfs)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Chart execution error: {e}\n\nGenerated code:\n{code}",
        )

    return {"chart": chart_json, "code": code}


@api_router.post("/chat")
async def chat(body: ChatRequest, x_api_key: str = Header(...)):
    """
    Conversational chat about all uploaded datasets.
    Implements a mini-agent loop: LLM can write Python code to inspect data, 
    we run it, and feed the output back to the LLM to formulate the final answer.
    """
    meta = _get_session(body.file_id)
    dfs  = _load_all_dataframes(meta)

    df_list = ", ".join(f"`{f['var_name']}` ({f['filename']})" for f in meta["files"])

    system_prompt = (
        "You are an expert data analyst and Python/Pandas specialist.\n"
        "You help users understand, explore, and answer specific questions about their datasets.\n"
        "IMPORTANT: You do not have the full data context, only the column names and 5 sample rows. "
        "If you need to perform calculations, filtering, or data extraction to answer the user's question accurately, "
        "you MUST write a Python script to do it. "
        "To run a Python script, output it in a code block like this:\n"
        "```python\nprint(df_queries['Impressions'].sum())\n```\n"
        "We will execute the script securely and give you back the printed output. Then you MUST use that output to answer the user naturally.\n"
        "ALWAYS use `print()` inside your Python scripts to output the results you need.\n"
        "If the user asks for 'the last X days', identify the Date column and calculate using `datetime.now()` or the max date in the data.\n"
        "Respond in the same language the user writes in.\n\n"
        f"Available DataFrames: {df_list}\n\n"
        "Dataset schemas and samples:\n" + _schema_prompt_block(meta)
    )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    
    final_reply_text = ""
    max_loops = 3
    
    for step in range(max_loops):
        try:
            reply = _call_llm(api_key=x_api_key, messages=messages, system_prompt=system_prompt)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM API error: {e}")

        messages.append({"role": "assistant", "content": reply})
        
        # Only add the reply text to the user-facing output if it contains useful info or if it's the final round
        final_reply_text += reply + "\n\n"
        
        # Check if LLM generated code to execute
        code_blocks = re.findall(r"```python\n(.*?)\n```", reply, re.DOTALL)
        if not code_blocks:
            break  # No code = final answer reached
            
        code = code_blocks[0]
        output = _safe_exec_data_code(code, dfs)
        
        # Format the execution output beautifully for the user
        final_reply_text += f"> **Execution Output:**\n> ```text\n> {output.strip()}\n> ```\n\n"
        
        # Feed the hidden output back into the LLM
        system_msg = f"System Execution Output:\n{output}\n\nPlease analyze this output and give the final answer to the user. Do not write more code unless absolutely necessary."
        messages.append({"role": "user", "content": system_msg})

    return {"reply": final_reply_text.strip()}


# Include the API router
app.include_router(api_router)

# Serve index.html specifically at root
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=(FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))

# Serve style.css specifically at root
@app.get("/style.css")
async def style():
    return FileResponse(FRONTEND_DIR / "style.css")

# Mount remaining static files as fallback
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
