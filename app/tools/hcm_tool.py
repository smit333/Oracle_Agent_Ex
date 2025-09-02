from __future__ import annotations

from typing import Any, Dict, List

from app.oracle.hcm_client import OracleHCMClient
from app.llm.schemas import APICall, ExecutionResult


class OracleHCMCallTool:
    """Executes a list of APICall instructions using OracleHCMClient."""

    def __init__(self, client: OracleHCMClient) -> None:
        self._client = client

    async def execute_calls(self, calls: List[APICall]) -> List[ExecutionResult]:
        results: List[ExecutionResult] = []
        for call in calls:
            try:
                try:
                    full_url = self._client.build_url(call.path)
                    print(f"[HCM_TOOL] Executing: {call.method} {full_url} params={call.params}")
                except Exception:
                    pass
                if call.method.upper() == "GET":
                    # Attempt pagination for GET calls; fall back to single page
                    data = await self._client.get_paginated(call.path, params=call.params)
                else:
                    data = await self._client.request_json(
                        call.method, call.path, params=call.params, json=call.body
                    )
                results.append(ExecutionResult(call=call, response=data))
            except Exception as e:  # noqa: BLE001 - bubble error message into result
                results.append(ExecutionResult(call=call, response={}, error=str(e)))
        return results

