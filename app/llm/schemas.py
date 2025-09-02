from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class APICall(BaseModel):
    description: str = Field(
        ..., description="Short purpose of this call, e.g., 'Fetch worker details'"
    )
    method: str = Field(..., description="HTTP method: GET, POST, PATCH, DELETE")
    path: str = Field(
        ..., description="Relative Oracle HCM REST path, e.g. /hcmRestApi/resources/latest/workers"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Query string parameters"
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON payload for non-GET methods"
    )


class Plan(BaseModel):
    intent: str = Field(..., description="One sentence describing user intent")
    api_calls: List[APICall] = Field(
        default_factory=list, description="Ordered list of API calls to execute"
    )


class ExecutionResult(BaseModel):
    call: APICall
    response: Dict[str, Any]
    error: Optional[str] = None


class AgentState(BaseModel):
    user_query: str
    user_context: Optional[Dict[str, Any]] = None
    plan: Optional[Plan] = None
    results: List[ExecutionResult] = Field(default_factory=list)
    answer: Optional[str] = None


# Sample Oracle HCM endpoints for testing
# Reference: Oracle HCM REST API docs
# https://docs.oracle.com/en/cloud/saas/human-resources/farws/index.html
SAMPLE_HCM_ENDPOINTS: List[APICall] = [
    APICall(
        description="Get all workers (versioned path)",
        method="GET",
        path="/hcmRestApi/resources/11.13.18.05/workers",
    ),
    APICall(
        description="Get all user accounts (versioned path)",
        method="GET",
        path="/hcmRestApi/resources/11.13.18.05/userAccounts",
    ),
    APICall(
        description="Get all absence records (versioned path)",
        method="GET",
        path="/hcmRestApi/resources/11.13.18.05/absenceRecords",
    ),
]


# Versioned endpoint catalog for planning and validation
# You can change the default version to match your HCM environment
HCM_API_DEFAULT_VERSION = "11.13.18.05"

HCM_API_ENDPOINTS = {
    "Users": {
        "listUserAccounts": {
            "method": "GET",
            "path": "/hcmRestApi/resources/{version}/userAccounts",
            "description": "List user accounts.",
            "queryParams": [],
            "responseFields": [
                "UserId",
                "Username",
                "SuspendedFlag",
                "PersonId",
                "PersonNumber",
                "GUID",
                "CreationDate",
                "LastUpdateDate",
            ],
        },
        "getUserAccountByGUID": {
            "method": "GET",
            "path": "/hcmRestApi/resources/{version}/userAccounts/{GUID}",
            "description": "Get a user account by GUID.",
            "queryParams": [],
            "responseFields": [
                "UserId",
                "Username",
                "SuspendedFlag",
                "PersonId",
                "PersonNumber",
                "GUID",
                "CreationDate",
                "LastUpdateDate",
            ],
        },
    }
}


def render_endpoint_path(path_template: str, version: str | None = None, **path_params: str) -> str:
    """Fill {version} and other placeholders in an endpoint path template.

    Example:
        render_endpoint_path("/hcmRestApi/resources/{version}/absences/{AbsenceId}", AbsenceId="123")
    """
    final_version = (version or HCM_API_DEFAULT_VERSION) or "latest"
    path = path_template.replace("{version}", final_version)
    for key, value in (path_params or {}).items():
        path = path.replace("{" + key + "}", str(value))
    return path

