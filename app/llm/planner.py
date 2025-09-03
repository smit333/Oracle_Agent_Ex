from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI

from app.llm.schemas import (
    Plan,
    HCM_API_ENDPOINTS,
    HCM_API_DEFAULT_VERSION,
    render_endpoint_path,
)


PLANNER_SYSTEM = """
You are a planning assistant that maps natural language Oracle HCM questions to
concrete REST calls. You MUST use ONLY the endpoints from the provided catalog
and only the allowed query parameters for each endpoint. Do NOT invent paths or
parameters. Use version 11.13.18.05 in all paths.

Rules:
- Allowed endpoints are given in a JSON catalog. Use only those.
- Allowed query params are those listed for the chosen endpoint. If none are
  listed, do not include any params.
- Do not include fields/expand/limit unless they are explicitly listed for that
  endpoint (they are not, so omit them).
- If multiple steps are needed, return multiple calls in order.
"""


PLANNER_USER = """
User query:
{user_query}

User context (identifiers that MAY be used for allowed query params):
{user_context}

Use ONLY this endpoint catalog (JSON):
{endpoint_catalog}

Return a Plan with intent and one or more api_calls.
Paths MUST use version 11.13.18.05, e.g. "/hcmRestApi/resources/11.13.18.05/workers".
Include only allowed query params for the chosen endpoint; otherwise omit params.
If user_context contains an allowed param key (e.g., PersonNumber, PersonId), you MAY use it.
"""


def create_planner(google_api_key: str, provider: str | None = None, azure_cfg: dict | None = None):
    provider_normalized = (provider or "gemini").lower()
    if provider_normalized == "azure":
        azure = azure_cfg or {}
        return AzureChatOpenAI(
            azure_endpoint=azure.get("endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=azure.get("api_key") or os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=azure.get("api_version") or os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
            deployment_name=azure.get("deployment") or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
            temperature=0.2,
        )
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=google_api_key, temperature=0.2)


async def plan_calls(llm, user_query: str, user_context: Optional[Dict[str, Any]] = None) -> Plan:
    parser = PydanticOutputParser(pydantic_object=Plan)
    prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_SYSTEM),
        ("user", PLANNER_USER + "\n\nFormat strictly as JSON matching the Plan schema:\n{format_instructions}"),
    ]).partial(
        format_instructions=parser.get_format_instructions(),
        endpoint_catalog=HCM_API_ENDPOINTS,
    )

    chain = prompt | llm | parser
    plan: Plan = await chain.ainvoke({
        "user_query": user_query,
        "user_context": user_context or {},
    })
    return _constrain_plan_to_catalog(plan)


def _match_catalog_entry(path: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """Return (group, key, entry) for the first catalog endpoint whose path template
    matches the given path ignoring the version and placeholders.
    """
    normalized = path.replace("/resources/latest/", f"/resources/{HCM_API_DEFAULT_VERSION}/")
    for group, entries in HCM_API_ENDPOINTS.items():
        for key, entry in entries.items():
            template: str = entry.get("path", "")
            templ_norm = template.replace("{version}", HCM_API_DEFAULT_VERSION)
            # Compare by prefix up to resource name
            if normalized.startswith(templ_norm.split("{")[0]):
                return group, key, entry
    return None


def _force_version(path: str) -> str:
    import re  # local import to avoid global namespace noise

    return re.sub(r"/resources/[^/]+/", f"/resources/{HCM_API_DEFAULT_VERSION}/", path)


def _constrain_plan_to_catalog(plan: Plan) -> Plan:
    # Enforce version and allowed params; drop anything not allowed
    for call in plan.api_calls:
        call.path = _force_version(call.path)
        matched = _match_catalog_entry(call.path)
        if not matched:
            # If not matched, still enforce version and clear params to be safe
            call.params = {}
            continue
        _group, _key, entry = matched
        allowed_params = set(entry.get("queryParams", []) or [])
        if not allowed_params:
            call.params = {}
        else:
            call.params = {k: v for k, v in (call.params or {}).items() if k in allowed_params}
        # Ensure no body for GET by default
        if call.method.upper() == "GET":
            call.body = None
    return plan

