from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.graph.agent import build_graph
from app.config import load_config
from app.oracle.hcm_client import OracleHCMClient
from app.llm.schemas import AgentState


app = FastAPI(title="Oracle HCM AI Agent")
graph = build_graph()
cfg = load_config()
hcm_client_for_routes = OracleHCMClient(cfg.hcm)


INDEX_HTML = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Oracle HCM AI Agent</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }
      #chat { max-width: 800px; margin: 0 auto; }
      .msg { padding: 10px 12px; border-radius: 8px; margin: 8px 0; }
      .user { background: #eef; }
      .bot { background: #efe; }
      #input { display: flex; gap: 8px; }
      textarea { flex: 1; padding: 8px; }
      button { padding: 8px 12px; }
    </style>
  </head>
  <body>
    <div id="chat">
      <h2>Oracle HCM AI Agent</h2>
      <div style="margin-bottom: 8px;">
        <select id="userSelect"></select>
        <button id="refreshUsers">Refresh users</button>
      </div>
      <div id="messages"></div>
      <div id="input">
        <textarea id="q" rows="3" placeholder="Ask about workers, jobs, assignments..."></textarea>
        <button id="send">Send</button>
      </div>
    </div>
    <script>
      const messages = document.getElementById('messages');
      function add(role, text) {
        const div = document.createElement('div');
        div.className = 'msg ' + (role === 'user' ? 'user' : 'bot');
        div.textContent = text;
        messages.appendChild(div);
        window.scrollTo(0, document.body.scrollHeight);
      }
      async function loadUsers() {
        try {
          const res = await fetch('/users');
          const data = await res.json();
          const sel = document.getElementById('userSelect');
          sel.innerHTML = '';
          (data.items || []).forEach(u => {
            const opt = document.createElement('option');
            opt.value = JSON.stringify(u);
            opt.textContent = u.label || `${u.Username} - ${u.PersonNumber}`;
            sel.appendChild(opt);
          });
        } catch (e) { console.error(e); }
      }

      document.getElementById('refreshUsers').onclick = loadUsers;
      loadUsers();

      document.getElementById('send').onclick = async () => {
        const q = document.getElementById('q').value.trim();
        if (!q) return;
        add('user', q);
        document.getElementById('q').value = '';
        let user_context = undefined;
        try {
          const sel = document.getElementById('userSelect');
          if (sel.value) user_context = JSON.parse(sel.value);
        } catch {}
        const res = await fetch('/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, user_context })
        });
        const data = await res.json();
        add('bot', data.answer || data.error || 'No response');
      };
    </script>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML


@app.post("/chat")
async def chat(body: Dict[str, Any]) -> Dict[str, Any]:
    query = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    user_ctx = body.get("user_context") or None
    state = AgentState(user_query=query, user_context=user_ctx)
    result = await graph.ainvoke(state)
    # LangGraph may return a dict-like state; normalize access
    if isinstance(result, dict):
        answer = result.get("answer")
        plan_obj = result.get("plan")
    else:
        answer = getattr(result, "answer", None)
        plan_obj = getattr(result, "plan", None)

    if plan_obj is not None and hasattr(plan_obj, "model_dump"):
        plan_dump = plan_obj.model_dump()
    else:
        plan_dump = plan_obj

    return {"answer": answer, "plan": plan_dump}


@app.get("/users")
async def list_users() -> Dict[str, Any]:
    try:
        data = await hcm_client_for_routes.request_json(
            "GET",
            "/hcmRestApi/resources/11.13.18.05/userAccounts",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    items = data.get("items", []) if isinstance(data, dict) else []
    mapped = []
    for it in items:
        mapped.append({
            "Username": it.get("Username"),
            "PersonNumber": it.get("PersonNumber"),
            "PersonId": it.get("PersonId"),
            "GUID": it.get("GUID"),
            "label": f"{it.get('Username')} - {it.get('PersonNumber')}",
        })
    return {"items": mapped}

