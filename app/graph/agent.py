from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import StateGraph, END

from app.config import load_config
from app.llm.schemas import AgentState
from app.llm.planner import create_planner, plan_calls
from app.llm.responder import create_responder, craft_response
from app.oracle.hcm_client import OracleHCMClient
from app.tools.hcm_tool import OracleHCMCallTool


def build_graph() -> Any:
    cfg = load_config()
    planner_llm = create_planner(
        cfg.google_api_key,
        provider=cfg.llm_provider,
        azure_cfg={
            "endpoint": cfg.azure_endpoint,
            "api_key": cfg.azure_api_key,
            "api_version": cfg.azure_api_version,
            "deployment": cfg.azure_chat_deployment,
        },
    )
    responder_llm = create_responder(
        cfg.google_api_key,
        provider=cfg.llm_provider,
        azure_cfg={
            "endpoint": cfg.azure_endpoint,
            "api_key": cfg.azure_api_key,
            "api_version": cfg.azure_api_version,
            "deployment": cfg.azure_chat_deployment,
        },
    )
    hcm_client = OracleHCMClient(cfg.hcm)
    hcm_tool = OracleHCMCallTool(hcm_client)

    graph = StateGraph(AgentState)

    async def node_plan(state: AgentState) -> AgentState:
        print("\n=== PLANNER INPUT ===")
        print(state.user_query)
        plan = await plan_calls(planner_llm, state.user_query, state.user_context)
        try:
            print("=== PLANNER OUTPUT (Plan) ===")
            print(plan.model_dump_json(indent=2))
        except Exception:
            pass
        state.plan = plan
        return state

    async def node_execute(state: AgentState) -> AgentState:
        if not state.plan:
            return state
        print("=== EXECUTOR START ===")
        for idx, c in enumerate(state.plan.api_calls, start=1):
            try:
                print(f"Call {idx}: {c.method} {c.path} params={c.params} body={(c.body or {})}")
            except Exception:
                pass
        results = await hcm_tool.execute_calls(state.plan.api_calls)
        try:
            print("=== EXECUTOR RESULTS (summaries) ===")
            for idx, r in enumerate(results, start=1):
                snippet = str(r.response)[:400]
                print(f"Result {idx}: error={r.error} snippet={snippet}")
        except Exception:
            pass
        state.results = results
        return state

    async def node_respond(state: AgentState) -> AgentState:
        answer = await craft_response(responder_llm, state.user_query, state.results)
        try:
            print("=== RESPONDER OUTPUT (Answer) ===")
            print(answer)
        except Exception:
            pass
        state.answer = answer
        return state

    graph.add_node("plan", node_plan)
    graph.add_node("execute", node_execute)
    graph.add_node("respond", node_respond)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "respond")
    graph.add_edge("respond", END)

    return graph.compile()

