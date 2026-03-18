**SRS — AI Data Analysis Tool**  v1.0.0

**SOFTWARE REQUIREMENTS SPECIFICATION**

**AI-Powered Data Analysis Tool**

*Intelligent CSV/Excel Analyzer with Dynamic Visualization & Conversational Chat*

|**Version**|1\.0.0|
| :- | :- |
|**Status**|Draft — For Review|
|**Date**|March 15, 2026|
|**Author**|Senior Fullstack Architect|
|**Classification**|Internal / Confidential|


# **Table of Contents**





# **1. Project Overview & Goals**

## **1.1 Executive Summary**
This document defines the Software Requirements Specification (SRS) for an AI-Powered Data Analysis Tool — a web application embeddable into any existing landing page that enables non-technical users to upload structured data files (CSV, XLSX) and interact with them through two complementary AI-driven interfaces: a Dynamic Visualizer and a Conversational Chat Window.

|<p>**Core Value Proposition**</p><p>Transform raw spreadsheet data into instant insights — no SQL, no scripting, no data-science background required. The user uploads a file, types a question in plain English, and the system responds with interactive charts or natural-language analysis in seconds.</p>|
| :- |

## **1.2 Project Goals**
- Deliver a dual-interface experience: chart generation and open-ended data chat in a single, unified UI.
- Support the three leading commercial LLM providers (OpenAI, Anthropic, Google Gemini) via user-supplied API keys.
- Achieve sub-5-second response times for standard datasets (up to 50,000 rows) through intelligent token optimization.
- Ensure zero data persistence between sessions: all uploaded files are purged from disk upon session expiry or browser close.
- Provide a fully English-language interface that can be embedded as an iframe or standalone route on any existing server.
- Maintain security best practices: API keys stored only in the browser session, never logged or persisted server-side.

## **1.3 Target Users**

|**User Role**|**Use Case**|
| :- | :- |
|Marketing Analysts|Upload campaign data CSVs, visualize traffic by channel, ask 'Which UTM source had the highest conversion rate?'|
|Sales Managers|Upload CRM exports, generate pipeline bar charts, ask 'Why did sales drop in Q3?'|
|Operations Teams|Upload logistics data, request heatmaps, ask 'Which routes have the most delays?'|
|Product Managers|Upload event tracking exports, visualize feature adoption, ask 'Which user cohort retains best?'|

## **1.4 Scope**
- IN SCOPE: File upload (CSV/XLSX), schema inference, chart generation via Plotly.js, conversational AI chat, multi-provider LLM support, session-based security, REST API backend.
- OUT OF SCOPE: Multi-user collaboration, persistent storage of user data, database connectors (SQL/NoSQL), real-time streaming data, mobile native apps.


# **2. System Architecture**

## **2.1 High-Level Architecture Overview**
The system follows a clean three-tier architecture: a browser-based Single-Page Application (SPA) frontend, a Python/FastAPI backend server, and external AI provider APIs. The design is intentionally stateless at the AI-processing layer — no conversation history or file data is stored beyond the active session.

|<p>**Architecture Pattern**</p><p>Stateless REST API + Session-Scoped File Storage + Client-Side State Management. The backend acts as a secure orchestration layer between the browser and the AI providers, never storing API keys or file data permanently.</p>|
| :- |

## **2.2 Component Breakdown**
### **2.2.1 Frontend Layer (Browser SPA)**
- Technology: Vanilla JS / React (developer choice), served as static files.
- File Upload Module: Drag-and-drop zone + file picker; validates MIME type and file size (<50 MB) before upload.
- API Key Manager: Secure in-memory form (never localStorage). Provider selector dropdown (OpenAI / Anthropic / Gemini). Key is transmitted via request header on each API call.
- Dual Panel Layout: Left panel = Visualizer with Plotly.js chart area and prompt input. Right panel = Chat window with message history and text input.
- State: Session-scoped JavaScript object tracking: current file ID, selected provider, conversation history, rendered charts.

### **2.2.2 Backend Layer (Python FastAPI)**
- Handles multipart file uploads; stores files in a temp directory with a UUID-keyed filename.
- Parses CSV/XLSX using Pandas; extracts schema (column names, dtypes, sample rows) for LLM context.
- Routes requests to the appropriate AI provider SDK based on the X-Provider and X-Api-Key headers.
- Generates and executes Python/Pandas code dynamically using a sandboxed exec() environment.
- Converts Pandas outputs to Plotly JSON traces for frontend rendering.
- Registers a background cleanup task (APScheduler) to delete temp files after 30 minutes of inactivity.

### **2.2.3 AI Provider Layer (External APIs)**
- OpenAI: gpt-4o / gpt-4-turbo via openai Python SDK.
- Anthropic: claude-opus-4 / claude-sonnet-4 via anthropic Python SDK.
- Google: gemini-1.5-pro / gemini-2.0-flash via google-generativeai Python SDK.
- Each provider is wrapped in a unified LLMClient interface with a single complete(prompt, system) method.

## **2.3 Data Flow — Chart Generation**

|**Step**|**Description**|
| :- | :- |
|Step 1|User types a chart prompt: 'Bar chart of sales by region'|
|Step 2|Frontend sends POST /api/chart with: {file\_id, prompt, provider} + API key header|
|Step 3|Backend loads the schema + 5-row sample from the cached file metadata|
|Step 4|Backend constructs a system prompt instructing the LLM to write Pandas + Plotly Express code|
|Step 5|LLM returns a Python code block|
|Step 6|Backend executes the code in a sandboxed exec() with only Pandas and Plotly in scope|
|Step 7|The Plotly Figure object is serialized to JSON using fig.to\_json()|
|Step 8|JSON is returned to frontend; Plotly.react() renders the interactive chart|

## **2.4 Data Flow — Conversational Chat**

|**Step**|**Description**|
| :- | :- |
|Step 1|User types a question: 'Why did revenue drop in March?'|
|Step 2|Frontend sends POST /api/chat with: {file\_id, question, history[], provider} + API key header|
|Step 3|Backend prepends the schema + sample as system context (token-optimized, not full file)|
|Step 4|Conversation history (last N turns) appended to stay within token limits|
|Step 5|LLM generates a natural-language response, optionally including a code snippet if calculation needed|
|Step 6|If code is detected in response, backend optionally executes it and appends computed result|
|Step 7|Final answer returned as JSON; frontend renders in the chat panel with Markdown formatting|


# **3. Functional Requirements**

## **3.1 FR-001 — File Upload**

|**ID**|**Requirement**|**Priority**|
| :- | :- | :- |
|FR-001.1|The system SHALL accept CSV files with .csv extension and MIME type text/csv.|MUST|
|FR-001.2|The system SHALL accept Excel files with .xlsx extension and MIME type application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.|MUST|
|FR-001.3|The system SHALL reject files larger than 50 MB with error code 413 and a user-friendly message.|MUST|
|FR-001.4|The system SHALL infer column names, data types (int, float, str, datetime), and generate a 5-row sample preview.|MUST|
|FR-001.5|The system SHALL assign a UUID v4 as the file\_id and store the file in /tmp/{file\_id}/data.{ext}.|MUST|
|FR-001.6|The system SHALL return the inferred schema as JSON within 3 seconds for files up to 50 MB.|MUST|
|FR-001.7|The system SHOULD display a column preview table in the UI immediately after upload.|SHOULD|
|FR-001.8|The system SHOULD detect and warn the user if the file contains no headers or only one column.|SHOULD|
|FR-001.9|The system MAY support multi-sheet Excel files; the user can select which sheet to analyze.|MAY|

## **3.2 FR-002 — API Key Management**

|**ID**|**Requirement**|**Priority**|
| :- | :- | :- |
|FR-002.1|The system SHALL provide a provider selection dropdown with options: OpenAI, Anthropic, Gemini.|MUST|
|FR-002.2|The system SHALL accept the API key via a password-type input field (characters masked).|MUST|
|FR-002.3|The system SHALL transmit the API key exclusively via the X-Api-Key HTTP header; it SHALL NOT be included in the request body or URL parameters.|MUST|
|FR-002.4|The system SHALL NOT log, store, or cache the API key on the server side under any circumstances.|MUST|
|FR-002.5|The system SHALL validate the API key format client-side (regex: OpenAI starts with sk-, Anthropic with sk-ant-, Gemini is 39 chars alphanumeric).|MUST|
|FR-002.6|The system SHALL clear the API key from memory when the user closes the tab or explicitly clicks 'Clear Key'.|MUST|
|FR-002.7|The system SHOULD display the active provider name in the header/status bar when a key is set.|SHOULD|
|FR-002.8|The system SHOULD support switching providers mid-session without requiring file re-upload.|SHOULD|

## **3.3 FR-003 — Chart Generation (Dynamic Visualizer)**

|**ID**|**Requirement**|**Priority**|
| :- | :- | :- |
|FR-003.1|The system SHALL accept a free-text chart prompt from the user (max 500 characters).|MUST|
|FR-003.2|The system SHALL generate valid Python code using Pandas and Plotly Express to fulfill the prompt.|MUST|
|FR-003.3|The system SHALL execute generated code in a sandboxed exec() with a restricted namespace containing only: pd (Pandas), px (Plotly Express), go (Plotly Graph Objects), and the loaded DataFrame df.|MUST|
|FR-003.4|The system SHALL serialize the resulting Plotly Figure to JSON using fig.to\_json() and return it.|MUST|
|FR-003.5|The frontend SHALL render the chart using Plotly.react() or Plotly.newPlot() with full interactivity (zoom, hover, export).|MUST|
|FR-003.6|The system SHALL return a structured error message if code execution fails, including a human-readable explanation.|MUST|
|FR-003.7|The system SHALL timeout code execution after 10 seconds and return a 408 error.|MUST|
|FR-003.8|The system SHOULD retry generation once with a corrective prompt if the first attempt fails.|SHOULD|
|FR-003.9|The system SHOULD support chart type hints in the prompt: 'bar', 'line', 'scatter', 'pie', 'heatmap', 'histogram', 'box'.|SHOULD|
|FR-003.10|The system MAY allow the user to download the rendered chart as PNG via the Plotly toolbar.|MAY|

## **3.4 FR-004 — Conversational Data Chat**

|**ID**|**Requirement**|**Priority**|
| :- | :- | :- |
|FR-004.1|The system SHALL maintain a conversation history of up to 20 turns per session.|MUST|
|FR-004.2|The system SHALL include the dataset schema and a 10-row sample as system context on every chat request.|MUST|
|FR-004.3|The system SHALL trim conversation history to the last 8 turns when the estimated token count exceeds 80% of the model's context window.|MUST|
|FR-004.4|The system SHALL render AI responses with Markdown formatting (bold, lists, code blocks, tables).|MUST|
|FR-004.5|The system SHALL display a 'Thinking...' typing indicator while the AI generates a response.|MUST|
|FR-004.6|The system SHALL support follow-up questions referencing previous answers (e.g., 'Can you show that as a chart?').|SHOULD|
|FR-004.7|The system SHOULD detect when the AI response contains a code snippet and offer a 'Run & Show Chart' button.|SHOULD|
|FR-004.8|The system SHOULD allow the user to copy any AI response to the clipboard.|SHOULD|
|FR-004.9|The system MAY support export of the entire chat history as a .txt or .md file.|MAY|

## **3.5 FR-005 — Session & State Management**
- The system SHALL generate a unique session token (UUID v4) on first page load, stored in sessionStorage.
- The system SHALL associate all uploaded files, conversation history, and settings with the session token.
- The system SHALL expire sessions after 30 minutes of inactivity and automatically delete associated files.
- The system SHALL provide a 'New Session' / 'Reset' button that clears all state and uploaded files.
- The system SHALL display a session expiry warning banner 5 minutes before automatic cleanup.


# **4. Technical Stack & API Endpoints**

## **4.1 Technology Stack**

|**Layer / Component**|**Technology & Notes**|
| :- | :- |
|Frontend Framework|React 18 (or Vanilla JS — developer choice). No heavy framework required.|
|Charting Library|Plotly.js v2.x (CDN or npm). Renders interactive charts from JSON traces.|
|Markdown Renderer|marked.js + DOMPurify for safe Markdown-to-HTML rendering in chat.|
|HTTP Client|Fetch API (native) or Axios for REST calls to the backend.|
|Backend Framework|Python 3.11+ with FastAPI 0.111+|
|ASGI Server|Uvicorn with Gunicorn workers for production deployment.|
|Data Processing|Pandas 2.x for CSV/XLSX parsing, schema inference, and DataFrame operations.|
|Code Execution|Python built-in exec() with restricted namespace + threading.Timer for timeout.|
|AI Provider SDKs|openai>=1.30, anthropic>=0.28, google-generativeai>=0.7|
|Task Scheduler|APScheduler 3.x for background session/file cleanup tasks.|
|CORS Middleware|FastAPI CORSMiddleware; allowed origins configured per environment.|
|Containerization|Docker + docker-compose (optional, for deployment consistency).|

## **4.2 REST API Endpoints**
### **4.2.1 File Management**

|**Endpoint**|**Description**|
| :- | :- |
|POST /api/upload|Upload CSV or XLSX file. Returns: {file\_id, schema, sample\_rows[], row\_count, col\_count}. Body: multipart/form-data with key 'file'.|
|DELETE /api/files/{file\_id}|Manually delete a file before session expiry. Returns: {deleted: true}.|
|GET /api/files/{file\_id}/schema|Retrieve the inferred schema for a previously uploaded file.|

### **4.2.2 Chart Generation**

|**Endpoint**|**Description**|
| :- | :- |
|POST /api/chart|Generate and execute a chart. Body: {file\_id, prompt}. Headers: X-Provider, X-Api-Key. Returns: {plotly\_json, code\_used, execution\_time\_ms}.|
|POST /api/chart/retry|Retry failed chart with corrective context. Body: {file\_id, prompt, previous\_error}. Same headers.|

### **4.2.3 Conversational Chat**

|**Endpoint**|**Description**|
| :- | :- |
|POST /api/chat|Send a chat message. Body: {file\_id, message, history[]}. Headers: X-Provider, X-Api-Key. Returns: {reply, tokens\_used, has\_code}.|
|POST /api/chat/execute|Execute a code snippet from a chat response. Body: {file\_id, code}. Returns: {result\_text, plotly\_json?}.|

### **4.2.4 Session Management**

|**Endpoint**|**Description**|
| :- | :- |
|POST /api/session|Create a new session. Returns: {session\_id, expires\_at}.|
|DELETE /api/session/{session\_id}|Explicitly terminate session and purge all associated files.|
|GET /api/health|Health check endpoint. Returns: {status: 'ok', version}.|

## **4.3 Request & Response Examples**
### **POST /api/chart — Request**

|<p>**Headers:**</p><p>`  `X-Provider: openai</p><p>`  `X-Api-Key: sk-••••••••••••••••</p><p>**Body:**</p><p>`  `{ "file\_id": "a3f9...", "prompt": "Bar chart of revenue by region" }</p>|
| :- |

### **POST /api/chart — Response**

|{ "plotly\_json": "{...}", "code\_used": "fig = px.bar(df, x='region', y='revenue')", "execution\_time\_ms": 312 }|
| :- |


# **5. UI/UX Design Guide**

## **5.1 Design Philosophy**
The interface targets data professionals who need speed, clarity, and trust. The visual language is inspired by modern enterprise BI tools (Metabase, Retool, Linear) and developer-focused dashboards. The aesthetic is 'Clean Enterprise Dark' — high contrast, minimal chrome, maximum data density without feeling overwhelming.

## **5.2 Typography System**

|**Role**|**Font Family**|**Weight**|**Size**|**Usage**|
| :- | :- | :- | :- | :- |
|Primary UI|Inter|400 / 500 / 600|13px–16px|All body text, labels, inputs, messages|
|Display / Headers|Inter|700 / 800|20px–36px|Section headings, page titles, feature labels|
|Monospace / Data|JetBrains Mono|400 / 500|12px–14px|Code blocks, column names, JSON output, IDs|
|Numeric Data|JetBrains Mono|600|14px–18px|Chart axis labels, statistics, token counts|
|AI Response Body|Inter|400|14px|Chat message text, markdown rendering|

**Google Fonts Import URL:** https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap

## **5.3 Color Palette — Dark Mode Enterprise**
### **5.3.1 Core Backgrounds & Surfaces**

|**Token Name**|**HEX Code**|**Role**|
| :- | :- | :- |
|--bg-base|#0F172A|App background, outermost shell|
|--bg-surface|#1E293B|Cards, panels, sidebars, modals|
|--bg-elevated|#253347|Dropdowns, tooltips, hover states|
|--bg-input|#162032|Input fields, textareas|
|--border-subtle|#334155|Dividers, card borders, table borders|
|--border-strong|#475569|Active inputs, focused elements|

### **5.3.2 Text Colors**

|**Token Name**|**HEX Code**|**Role**|
| :- | :- | :- |
|--text-primary|#F1F5F9|Primary body text, headings|
|--text-secondary|#CBD5E1|Subtitles, descriptions, metadata|
|--text-muted|#94A3B8|Placeholders, timestamps, disabled text|
|--text-inverse|#0F172A|Text on light/colored backgrounds|

### **5.3.3 Brand & Accent Colors**

|**Token Name**|**HEX Code**|**Role**|
| :- | :- | :- |
|--accent-primary|#4F8EF7|Primary CTAs, active nav items, links|
|--accent-secondary|#6C63FF|Secondary actions, AI badge, gradient stops|
|--accent-sky|#38BDF8|Highlight, info states, chart axis|
|--accent-violet|#818CF8|Chart secondary series, hover states|
|--success|#34D399|Upload success, valid inputs, positive trends|
|--warning|#FBBF24|Session expiry warnings, token limit alerts|
|--danger|#F87171|Errors, invalid files, failed generation|
|--chart-1|#4F8EF7|Plotly trace color 1|
|--chart-2|#34D399|Plotly trace color 2|
|--chart-3|#FBBF24|Plotly trace color 3|
|--chart-4|#818CF8|Plotly trace color 4|
|--chart-5|#F87171|Plotly trace color 5|
|--chart-6|#38BDF8|Plotly trace color 6|

## **5.4 Layout Structure**
### **5.4.1 Page Layout**
- Top Navigation Bar (56px): App logo, active file name badge, provider status indicator, 'New Session' button, 'Upload File' button.
- Main Content Area: Two-column split layout. Left column (55%) = Dynamic Visualizer Panel. Right column (45%) = Conversational Chat Panel.
- Each panel has its own scrollable content area and sticky input bar at the bottom.
- Responsive breakpoint: below 1024px width, the panels stack vertically (Visualizer on top, Chat below).

### **5.4.2 Visualizer Panel**
- Prompt Input Bar: Full-width text input with placeholder 'Describe a chart... (e.g., Bar chart of sales by region)'. Send button with arrow icon.
- Chart Area: Empty state shows a centered illustration and text 'Your chart will appear here'. When a chart is rendered, Plotly fills the entire area with its built-in toolbar (zoom, pan, download PNG).
- Code Inspector (collapsible): Small toggle below the chart shows the AI-generated Python code that produced it. Rendered in JetBrains Mono with syntax highlighting.

### **5.4.3 Chat Panel**
- Message List: Scrollable area with alternating user and AI message bubbles. User messages are right-aligned with --accent-primary background. AI messages are left-aligned with --bg-elevated background and a small AI provider icon.
- Markdown rendering: AI responses support bold, italics, inline code, code blocks, bullet lists, and numbered lists.
- Input Bar: Multi-line textarea (grows up to 5 lines). 'Send' button + keyboard shortcut: Cmd/Ctrl + Enter. Character counter (max 2000 chars).
- Token Usage Footer: Small indicator showing estimated tokens used in the current context window. Color coded: green <50%, amber 50-80%, red >80%.

## **5.5 Component Design Tokens**

|**Component**|**CSS Variable / Value**|
| :- | :- |
|Border Radius (cards)|--radius-card: 12px|
|Border Radius (buttons)|--radius-btn: 8px|
|Border Radius (inputs)|--radius-input: 8px|
|Border Radius (chips)|--radius-chip: 20px|
|Shadow (card)|box-shadow: 0 4px 24px rgba(0,0,0,0.3)|
|Shadow (elevated)|box-shadow: 0 8px 40px rgba(0,0,0,0.45)|
|Transition speed|--transition: 200ms ease|
|Font size (sm)|--text-sm: 12px|
|Font size (base)|--text-base: 14px|
|Font size (lg)|--text-lg: 16px|
|Spacing unit|--space: 8px (all spacing in multiples)|

## **5.6 UI Copy & Microcopy Guidelines**
- All user-facing strings MUST be in English. No Spanish, no mixed languages.
- Button labels: use verbs. 'Upload File' not 'File Upload'. 'Generate Chart' not 'Chart Generation'.
- Error messages must explain the problem AND suggest a fix. 'File too large (max 50 MB). Try splitting into smaller files.'
- Loading states: Avoid generic 'Loading...'. Use contextual messages: 'Analyzing your data...', 'Generating chart...', 'AI is thinking...'
- Empty states: Always include an illustration and a call-to-action. Never leave a blank panel with no guidance.


# **6. Security & Best Practices Manual**

## **6.1 File Handling & Lifecycle Management**

|<p>**Security Principle: Zero Persistence**</p><p>Uploaded data files must never survive beyond the active session. This is both a privacy requirement and a storage management necessity. Treat all uploaded files as temporary, ephemeral, and untrusted.</p>|
| :- |

### **6.1.1 Upload Security**
- Validate file type by MIME sniffing the file header bytes (magic numbers), not just the filename extension. A file renamed to data.csv that is actually an executable must be rejected.
- Hard cap file size at 50 MB server-side using FastAPI's UploadFile size check. Never trust client-side validation alone.
- Store uploaded files in an isolated directory (/tmp/uploads/{session\_id}/{file\_id}/) with no execute permissions (chmod 644 on Linux).
- Never serve uploaded files back to the browser via a public URL. Files are only accessed internally by the Python processing layer.
- Sanitize filenames: strip all non-alphanumeric characters except dots and hyphens before writing to disk.

### **6.1.2 Automatic File Deletion**
- Register a cleanup callback on session creation: files are deleted when the session expires (30-minute idle timeout).
- Implement a fallback cron job (APScheduler) that scans /tmp/uploads/ every 15 minutes and deletes any directory older than 60 minutes regardless of session state — catches orphaned files from server restarts.
- On explicit session reset (user clicks 'New Session') or browser tab close (via beforeunload event firing DELETE /api/session), trigger immediate file deletion.
- Log file creation and deletion events (file\_id, session\_id, timestamp) to an audit log. Do NOT log file contents.

### **6.1.3 Data Isolation**
- Each session\_id maps to a strictly isolated directory. File IDs are UUID v4s — unguessable and collision-proof.
- The backend must verify that the file\_id in every request belongs to the requesting session\_id. Cross-session file access must return 403 Forbidden.

## **6.2 API Key Security**

|<p>**Critical: API Keys Are User Property**</p><p>The application never has a reason to store, log, or cache a user's AI provider API key. Any code path that persists a key, even temporarily, is a critical security vulnerability.</p>|
| :- |

### **6.2.1 Client-Side Key Handling**
- Store the API key exclusively in a JavaScript variable within the React/JS component's state. NEVER write it to localStorage, sessionStorage, cookies, or any other persistent browser storage.
- When the user closes the browser tab, the variable is automatically garbage collected. Add an explicit window.addEventListener('beforeunload', ...) to null the variable for immediate GC.
- Mask the key input field with type='password'. After the user enters the key, only display the last 4 characters (e.g., ...f7K2) for confirmation; never show the full key again.
- Provide a visible 'Clear API Key' button that immediately wipes the key from state and resets the input field.

### **6.2.2 Server-Side Key Handling**
- Extract the API key from the X-Api-Key header at the start of each request handler.
- Pass the key directly to the provider SDK's constructor or method call — it should never be assigned to a module-level variable, class attribute, or any structure with a lifetime beyond the single request.
- The key must NOT appear in: application logs, error messages, stack traces, or debug output. Use structured logging with an allowlist of safe fields.
- Do NOT cache LLM client instances per-user. Instantiate a fresh client per request using the per-request API key.
- If a 401 Unauthorized response is received from the LLM provider, return a sanitized error to the frontend: 'Invalid API Key — please check your key and try again.' Do not forward the provider's raw error message.

## **6.3 Code Execution Safety (exec() Sandboxing)**

|<p>**High Risk: Dynamic Code Execution**</p><p>The exec() call is the highest-risk component in the system. A malicious prompt could inject code that reads sensitive server files, makes network calls, or exhausts resources. The sandbox below is mandatory.</p>|
| :- |

### **6.3.1 Restricted Namespace**
The exec() call must use an explicit, restrictive namespace dictionary:

|<p>safe\_globals = {</p><p>`    `"\_\_builtins\_\_": {},  # Disable ALL Python builtins</p><p>`    `"pd": pandas,        # Pandas only</p><p>`    `"px": plotly.express, # Plotly Express only</p><p>`    `"go": plotly.graph\_objects, # Graph Objects</p><p>`    `"df": user\_dataframe  # The loaded DataFrame</p><p>}</p><p>exec(generated\_code, safe\_globals)</p>|
| :- |

### **6.3.2 Additional Execution Controls**
- Wrap exec() in a threading.Timer with a 10-second timeout. If the thread does not complete, kill it and raise a TimeoutError.
- Limit memory usage of the exec environment using resource.setrlimit (Linux) or equivalent. Cap at 512 MB.
- The LLM system prompt must instruct the model to ONLY produce code that assigns a result to a variable named 'fig' (the Plotly Figure). Any code that does not produce 'fig' in the local namespace after execution is treated as failed.
- Log all generated code to an append-only audit log for forensic review. Tag with session\_id (not user identity) and timestamp.
- Implement a code static analysis pre-check using Python's ast module: reject any generated code containing: import statements, open() calls, subprocess references, \_\_class\_\_, \_\_globals\_\_, or any dunder attributes.

## **6.4 Token Optimization Strategy**

|<p>**Best Practice: Never Send the Full File to the LLM**</p><p>Sending all 50,000 rows of a dataset to an LLM is expensive, slow, and unnecessary. The LLM needs to understand the structure of the data and generate code — not memorize every row. Use the schema-and-sample pattern.</p>|
| :- |

### **6.4.1 Schema + Sample Pattern**
- After upload, extract and cache: (a) column names and inferred dtypes, (b) 10 representative sample rows (first 5 + last 5), (c) basic statistics per numeric column (min, max, mean, std, null count).
- This schema object is typically 500–1,500 tokens — compared to 50,000+ tokens for a full file.
- Include this schema in the system prompt for every request. The LLM uses it to write correct Pandas code without ever seeing the full data.

### **6.4.2 Conversation History Trimming**
- Track estimated token count of the conversation history after each turn.
- When history exceeds 60% of the model's context window, apply a rolling window: keep the system context (schema) + the last 8 complete turns. Summarize older turns into a 1-2 sentence 'Prior context' string prepended to the window.
- Display the current context window usage as a percentage in the chat footer so the user understands when history is being trimmed.

### **6.4.3 Model-Specific Context Windows**

|**Model**|**Context Window & Implications**|
| :- | :- |
|OpenAI gpt-4o|128,000 tokens — very generous; trimming rarely needed for typical sessions.|
|Anthropic claude-sonnet-4|200,000 tokens — highest context; schema + full 30-turn history easily fits.|
|Google gemini-1.5-pro|1,000,000 tokens — effectively unlimited for this use case; no trimming needed.|
|OpenAI gpt-4-turbo|128,000 tokens — equivalent to gpt-4o.|

## **6.5 HTTPS & Network Security**
- The application MUST be served exclusively over HTTPS in production. Never allow HTTP for any endpoint that accepts API keys.
- Set strict CORS origins in FastAPI: only allow the exact domain(s) where the frontend is hosted. Do not use wildcard (\*) origins.
- Implement rate limiting on all /api/\* endpoints: maximum 30 requests per minute per session token using slowapi or equivalent.
- Set security headers on all responses: X-Content-Type-Options: nosniff, X-Frame-Options: SAMEORIGIN (unless iframe embedding is required), Content-Security-Policy with a restrictive policy.
- Use HTTPS-only cookies for the session token if not using header-based auth.

## **6.6 Input Validation & Injection Prevention**
- Validate all incoming JSON request bodies with Pydantic models. Reject requests with unexpected fields.
- Limit prompt length to 500 characters for chart prompts and 2,000 characters for chat messages at both client and server side.
- The AI's system prompt must instruct it to only output Python code for chart generation requests. Include an instruction such as: 'You must only output a single Python code block. Do not include explanations, import statements, or file I/O. Only use the variables pd, px, go, and df.'
- Treat all LLM-generated code as untrusted input subject to the sandboxing controls in Section 6.3.

## **6.7 Compliance & Privacy Checklist**

|**Requirement**|**Implementation**|
| :- | :- |
|GDPR / Data Minimization|Do not collect or store any personally identifiable information. Session IDs are UUID v4s with no link to user identity.|
|Right to Erasure|Files are automatically deleted on session expiry. Manual deletion available via 'New Session' button and DELETE /api/session endpoint.|
|Data in Transit|All API calls use HTTPS/TLS 1.2+. API keys transmitted only via headers, never URL parameters.|
|Audit Logging|Log: session create/delete, file upload/delete, code execution (with code hash, not content). Never log file contents or API keys.|
|Third-Party Data|Inform users in the UI that their prompts and data samples are sent to the selected AI provider per that provider's privacy policy.|


# **Appendix A — Glossary**

|**Term**|**Definition**|
| :- | :- |
|SRS|Software Requirements Specification — this document.|
|LLM|Large Language Model — AI model used for text generation (GPT-4o, Claude, Gemini).|
|Schema|The structural description of a dataset: column names, data types, and basic statistics.|
|exec()|Python built-in function that executes a string as Python code in a given namespace.|
|Plotly JSON|A serialized Plotly Figure object in JSON format, used to render interactive charts in the browser via Plotly.js.|
|Session Token|A UUID v4 assigned to each browser session to isolate data and file access.|
|Token (LLM)|The basic unit of text processing for LLMs — approximately 0.75 English words. Pricing and context limits are measured in tokens.|
|MIME|Multipurpose Internet Mail Extensions — a standard that indicates the nature and format of a file.|
|DXA|Document eXtended Attribute units — used in DOCX format: 1440 DXA = 1 inch.|
|APScheduler|Advanced Python Scheduler — a library for scheduling background jobs in Python applications.|

# **Appendix B — Environment Variables**

|**Variable**|**Description**|
| :- | :- |
|APP\_ENV|production | development | test|
|ALLOWED\_ORIGINS|Comma-separated list of allowed CORS origins (e.g., https://yoursite.com)|
|UPLOAD\_DIR|Path to temp file storage directory (default: /tmp/uploads)|
|SESSION\_TIMEOUT\_MINS|Session idle timeout in minutes (default: 30)|
|MAX\_FILE\_SIZE\_MB|Maximum upload file size in MB (default: 50)|
|MAX\_EXEC\_TIMEOUT\_SECS|Maximum code execution timeout in seconds (default: 10)|
|LOG\_LEVEL|debug | info | warning | error|
|RATE\_LIMIT\_RPM|Max requests per minute per session (default: 30)|

*End of Document — SRS v1.0.0*
Confidential — Internal Use Only  |  Page   of  
