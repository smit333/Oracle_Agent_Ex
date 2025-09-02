from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

from app.config import HCMConfig


class OracleHCMClient:
    """Async HTTP client for Oracle Fusion Cloud HCM REST APIs.

    Supports Basic and OAuth Bearer authentication. Provides helper methods for
    JSON requests and simple pagination using `limit` and `offset` query params.
    """

    def __init__(self, config: HCMConfig) -> None:
        if not config.base_url:
            raise ValueError("HCM base_url is required")
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def build_url(self, path: str) -> str:
        url_path = path if path.startswith("/") else f"/{path}"
        return f"{self._config.base_url}{url_path}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            auth = None
            if self._config.auth_method == "basic":
                if not (self._config.username and self._config.password):
                    raise ValueError("Basic auth requires username and password")
                auth = httpx.BasicAuth(self._config.username, self._config.password)
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers=headers,
                auth=auth,
                timeout=httpx.Timeout(60.0, connect=15.0),
            )
        return self._client

    def _augment_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        result = dict(headers or {})
        if self._config.auth_method == "oauth":
            if not self._config.oauth_token:
                raise ValueError("OAuth selected but HCM_OAUTH_TOKEN is empty")
            result["Authorization"] = f"Bearer {self._config.oauth_token}"
        return result

    async def close(self) -> None:
        client = self._client
        if client is not None:
            await client.aclose()
            self._client = None

    async def request_json(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        client = await self._get_client()
        method_upper = method.upper()
        req_headers = self._augment_headers(headers)
        url_path = path if path.startswith("/") else f"/{path}"
        try:
            resp = await client.request(
                method_upper,
                url_path,
                params=params,
                json=json,
                headers=req_headers,
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error calling HCM {self.build_url(url_path)}: {e}") from e

        content_type = resp.headers.get("content-type", "")
        if resp.status_code >= 400:
            text = resp.text
            raise RuntimeError(
                f"HCM API error {resp.status_code} for {method_upper} {self.build_url(url_path)}: {text}"
            )
        if "application/json" in content_type:
            return resp.json()
        return {"status": resp.status_code, "content": resp.text}

    async def get_paginated(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """Fetch multiple pages via `limit` and `offset` query params.

        Aggregates `items` if present; otherwise returns a list of page payloads
        in `pages`.
        """
        all_items: list[Any] = []
        pages: list[Dict[str, Any]] = []

        base_params = dict(params or {})
        for page_index in range(max_pages):
            page_params = dict(base_params)
            page_params.setdefault("limit", page_size)
            page_params["offset"] = page_index * page_size
            data = await self.request_json("GET", path, params=page_params)
            if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                items = data["items"]
                all_items.extend(items)
                pages.append(data)
                if len(items) < page_size:
                    break
            else:
                pages.append(data)
                # No standard items field; stop after first response
                break
            # Avoid tight loop pressure
            await asyncio.sleep(0)

        if all_items:
            return {"items": all_items, "pages": pages}
        return {"pages": pages}

