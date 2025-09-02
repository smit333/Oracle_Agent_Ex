# Oracle HCM AI Agent (LangGraph + Gemini)

This project is an AI agent that plans and executes Oracle Fusion Cloud HCM REST API calls using LangGraph and Google Gemini, then replies with a concise natural-language answer in a minimal chat UI.

References:
- Oracle HCM REST overview: [Oracle HCM REST](https://docs.oracle.com/en/cloud/saas/human-resources/farws/index.html)
- User Accounts (collection): [GET /userAccounts](https://docs.oracle.com/en/cloud/saas/human-resources/farws/op-useraccounts-get.html)
- User Account by GUID (item): [GET /userAccounts/{GUID}](https://docs.oracle.com/en/cloud/saas/human-resources/farws/op-useraccounts-guid-get.html)

## Architecture
- Planner (Gemini) turns a user query and selected user context into a structured Plan of REST calls.
- Executor runs the REST calls against Oracle HCM (Basic Auth).
- Responder (Gemini) summarizes raw results for the chat UI.
- LangGraph orchestrates: plan → execute → respond.

## Key Files
- `app/config.py`: Loads environment variables (`.env`) and exposes config dataclasses.
- `app/oracle/hcm_client.py`: Async Oracle HCM REST client using httpx; Basic or OAuth (we use Basic). Builds full URLs and returns parsed JSON.
- `app/llm/schemas.py`:
  - `APICall`, `Plan`, `ExecutionResult`, `AgentState` data models.
  - `HCM_API_ENDPOINTS`: whitelisted endpoints the planner is allowed to use (currently only `userAccounts` list and by GUID, version `11.13.18.05`).
  - `render_endpoint_path()` helper for version/placeholder expansion.
- `app/tools/hcm_tool.py`: Executes a list of `APICall` items via the HCM client; returns `ExecutionResult[]`.
- `app/llm/planner.py`: Gemini prompt + Pydantic parsing. Constrained to the whitelisted catalog and version `11.13.18.05`. Strips disallowed params.
- `app/llm/responder.py`: Gemini prompt that converts raw execution results into a concise answer.
- `app/graph/agent.py`: Builds the LangGraph graph with three nodes: plan, execute, respond; emits debug logs for planner/executor/responder.
- `app/server/main.py`: FastAPI app with a simple HTML UI.
  - `GET /`: chat page with a dropdown of user accounts and a text box.
  - `GET /users`: returns `{ items: [ { Username, PersonNumber, PersonId, GUID, label } ] }` from HCM `/userAccounts`.
  - `POST /chat`: runs the agent with `{ query, user_context }`.

## Requirements
- Python 3.11+ (tested on Windows 11)
- Oracle HCM test environment with REST access (Basic auth)
- Google Gemini API key (free tier works, e.g., `gemini-1.5-flash`)

## Setup (Windows)
1. Create and activate a virtual environment
```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
```

2. Install dependencies
```powershell
pip install -r requirements.txt
```

3. Create `.env` at the project root (same folder as `requirements.txt`)
```bash
GOOGLE_API_KEY=your_gemini_api_key
HCM_BASE_URL=https://your-instance.oraclecloud.com
HCM_USERNAME=your_hcm_username
HCM_PASSWORD=your_hcm_password
PORT=8000
```
Notes:
- `HCM_BASE_URL` should not have a trailing slash.
- Authentication used here is Basic (username/password).

4. Run the server
```powershell
./venv/Scripts/python.exe -m uvicorn app.server.main:app --reload --port 8000
```
Open `http://127.0.0.1:8000`.

## Using the App
- Click “Refresh users” to load user accounts from `/hcmRestApi/resources/11.13.18.05/userAccounts`.
- Select a user (`Username - PersonNumber`). The selection is sent as `user_context` with each chat message.
- Ask questions like:
  - “list all users”
  - “get my user account” (uses `userAccounts/{GUID}` when available)

## How Planning Works (Constrained)
- The planner only uses endpoints in `HCM_API_ENDPOINTS` and forces version `11.13.18.05`.
- Disallowed query parameters are stripped automatically.
- Current catalog includes only:
  - `GET /hcmRestApi/resources/11.13.18.05/userAccounts`
  - `GET /hcmRestApi/resources/11.13.18.05/userAccounts/{GUID}`

## Debugging
- The terminal logs planner input/output, executor calls, and responder output.
- Errors from HCM show the absolute URL and server response.
- Gemini quota errors (429) can occur on the free tier; wait or reduce requests.

## Editor Tips (VS Code)
- Select the interpreter: `Python: Select Interpreter` → `venv\Scripts\python.exe`.
- If Pylance shows missing imports, reload the window after selecting the interpreter.

## Cleaning and Git Ignore
- `__pycache__/` and `*.pyc` are safe to delete; add to `.gitignore`:
```gitignore
__pycache__/
*.pyc
*.pyo
```

## Customization
- Change the Gemini model/temperature in:
  - `app/llm/planner.py` → `ChatGoogleGenerativeAI(model="gemini-1.5-flash", ...)`
  - `app/llm/responder.py` → `ChatGoogleGenerativeAI(model="gemini-1.5-flash", ...)`
- Expand `HCM_API_ENDPOINTS` to permit more resources. Update the UI/server as needed.

## Troubleshooting
- 400 errors like “URL request parameter X cannot be used” mean that parameter isn’t allowed for that endpoint. The planner is constrained not to add params for these two endpoints.
- If you want to pass identifiers, use the dropdown (GUID is ideal for the GUID endpoint).
- Ensure your Oracle user has privileges for the HCM REST APIs being called.

## License
For internal use; add your preferred license text here.
