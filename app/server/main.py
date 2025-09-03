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
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Oracle HCM AI Agent</title>
    <style>
      :root { color-scheme: light dark; }
      body { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #f6f7f9; color: #111; }
      .container { max-width: 980px; margin: 0 auto; display: flex; flex-direction: column; height: 100dvh; }
      .topbar { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #fff; border-bottom: 1px solid #e5e7eb; position: sticky; top: 0; z-index: 5; }
      .title { font-weight: 600; }
      .spacer { flex: 1; }
      select, button, textarea { border: 1px solid #d1d5db; border-radius: 8px; background: #fff; color: inherit; }
      select, button { padding: 8px 10px; }
      .chat { flex: 1; overflow: auto; padding: 16px; }
      .message { display: flex; gap: 12px; padding: 12px 14px; border-radius: 12px; margin: 10px 0; max-width: 85%; }
      .message.user { margin-left: auto; background: #e6f0ff; }
      .message.bot { margin-right: auto; background: #f0fdf4; }
      .avatar { width: 28px; height: 28px; border-radius: 50%; background: #e5e7eb; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; }
      .content { flex: 1; white-space: pre-wrap; }
      .content code { background: #1118270d; padding: 2px 4px; border-radius: 4px; }
      .footer { display: flex; gap: 10px; padding: 12px; background: #fff; border-top: 1px solid #e5e7eb; position: sticky; bottom: 0; }
      textarea { flex: 1; padding: 10px 12px; resize: vertical; min-height: 56px; }
      .meta { font-size: 12px; color: #6b7280; margin-top: 6px; }
      details.plan { margin-top: 6px; }
    </style>
    <script src=\"https://cdn.jsdelivr.net/npm/marked/marked.min.js\"></script>
  </head>
  <body>
    <div class=\"container\">
      <div class=\"topbar\">
        <div class=\"title\">Oracle HCM AI Agent</div>
        <div class=\"spacer\"></div>
        <select id=\"userSelect\" title=\"Select user\"></select>
        <button id=\"refreshUsers\">Refresh users</button>
        <button id=\"newChat\">New chat</button>
      </div>
      <div id=\"messages\" class=\"chat\"></div>
      <div class=\"footer\">
        <textarea id=\"q\" rows=\"3\" placeholder=\"Ask about user accounts, GUID details... (Shift+Enter for newline)\"></textarea>
        <button id=\"send\">Send</button>
      </div>
    </div>
    <script>
      const EL = {
        messages: document.getElementById('messages'),
        q: document.getElementById('q'),
        send: document.getElementById('send'),
        userSelect: document.getElementById('userSelect'),
        refreshUsers: document.getElementById('refreshUsers'),
        newChat: document.getElementById('newChat'),
      };

      function renderMessage(role, text, plan) {
        const wrap = document.createElement('div');
        wrap.className = 'message ' + (role === 'user' ? 'user' : 'bot');
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';
        const content = document.createElement('div');
        content.className = 'content';
        try { content.innerHTML = marked.parse(text || ''); } catch { content.textContent = text || ''; }
        wrap.appendChild(avatar);
        wrap.appendChild(content);
        if (plan) {
          const det = document.createElement('details');
          det.className = 'plan';
          const sum = document.createElement('summary');
          sum.textContent = 'Show plan';
          const pre = document.createElement('pre');
          pre.textContent = JSON.stringify(plan, null, 2);
          det.appendChild(sum); det.appendChild(pre);
          content.appendChild(det);
        }
        EL.messages.appendChild(wrap);
        EL.messages.scrollTop = EL.messages.scrollHeight;
      }

      async function loadUsers() {
        try {
          const res = await fetch('/users');
          const data = await res.json();
          const sel = EL.userSelect; sel.innerHTML = '';
          (data.items || []).forEach(u => {
            const opt = document.createElement('option');
            opt.value = JSON.stringify(u);
            opt.textContent = u.label || `${u.Username} - ${u.PersonNumber}`;
            sel.appendChild(opt);
          });
        } catch (e) { console.error(e); }
      }

      EL.refreshUsers.onclick = loadUsers;
      loadUsers();

      EL.newChat.onclick = () => {
        EL.messages.innerHTML = '';
        EL.q.value = '';
        EL.q.focus();
      };

      EL.q.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          EL.send.click();
        }
      });

      EL.send.onclick = async () => {
        const q = EL.q.value.trim();
        if (!q) return;
        renderMessage('user', q);
        EL.q.value = '';
        let user_context = undefined;
        try {
          const sel = EL.userSelect;
          if (sel.value) user_context = JSON.parse(sel.value);
        } catch {}
        const res = await fetch('/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, user_context })
        });
        const data = await res.json();
        renderMessage('bot', data.answer || data.error || 'No response', data.plan || null);
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

