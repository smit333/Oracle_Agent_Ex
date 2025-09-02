from __future__ import annotations

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.llm.schemas import ExecutionResult


RESPONDER_SYSTEM = """
You are a helpful assistant for Oracle HCM users. You will receive the user's
original query and raw API results. Produce a concise, accurate, and polite
natural language answer. If results are empty, state what was attempted and any
next steps or checks.
"""

RESPONDER_USER = """
User query:
{user_query}

Executed results (JSON snippets):
{results_summary}

Provide a final answer suitable for display in a chat UI.
"""


def create_responder(google_api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=google_api_key, temperature=0.3)


async def craft_response(llm: ChatGoogleGenerativeAI, user_query: str, results: List[ExecutionResult]) -> str:
    def summarize() -> str:
        parts = []
        for r in results:
            err = f" error={r.error}" if r.error else ""
            snippet = str(r.response)[:1200]
            parts.append(f"- {r.call.method} {r.call.path}{err}\n  params={r.call.params}\n  body={(r.call.body or {})}\n  resp_snippet={snippet}")
        return "\n".join(parts) if parts else "(no results)"

    prompt = ChatPromptTemplate.from_messages([
        ("system", RESPONDER_SYSTEM),
        ("user", RESPONDER_USER),
    ])
    chain = prompt | llm
    msg = await chain.ainvoke({
        "user_query": user_query,
        "results_summary": summarize(),
    })
    return msg.content if hasattr(msg, "content") else str(msg)

