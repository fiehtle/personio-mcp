#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import copy
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP

AUTH_PATHS = {"/v2/auth/token", "/v2/auth/revoke"}
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")


def get_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class PersonioTokenManager:
    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        default_scope: str | None,
        app_id: str,
        partner_id: str | None,
        timeout_seconds: float,
        refresh_buffer_seconds: int,
    ) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.default_scope = default_scope
        self.app_id = app_id
        self.partner_id = partner_id
        self.timeout_seconds = timeout_seconds
        self.refresh_buffer_seconds = refresh_buffer_seconds

        self._cached_token: str | None = None
        self._cached_scope: str | None = None
        self._expires_at_epoch: float = 0.0
        self._async_lock: asyncio.Lock | None = None

    @property
    def cached_token(self) -> str | None:
        return self._cached_token

    @property
    def expires_at_epoch(self) -> float:
        return self._expires_at_epoch

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "X-Personio-App-ID": self.app_id,
        }
        if self.partner_id:
            headers["X-Personio-Partner-ID"] = self.partner_id
        return headers

    def _has_valid_cached_token(self, requested_scope: str | None) -> bool:
        if not self._cached_token:
            return False
        if requested_scope and requested_scope != self._cached_scope:
            return False
        return (time.time() + self.refresh_buffer_seconds) < self._expires_at_epoch

    async def _ensure_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    async def obtain_token(
        self,
        *,
        scope: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        requested_scope = scope or self.default_scope

        if not force_refresh and self._has_valid_cached_token(requested_scope):
            return {
                "access_token": self._cached_token,
                "token_type": "Bearer",
                "expires_in": max(0, int(self._expires_at_epoch - time.time())),
                "scope": self._cached_scope,
                "cached": True,
            }

        async_lock = await self._ensure_lock()
        async with async_lock:
            if not force_refresh and self._has_valid_cached_token(requested_scope):
                return {
                    "access_token": self._cached_token,
                    "token_type": "Bearer",
                    "expires_in": max(0, int(self._expires_at_epoch - time.time())),
                    "scope": self._cached_scope,
                    "cached": True,
                }

            form: dict[str, str] = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            if requested_scope:
                form["scope"] = requested_scope

            headers = self._headers()
            headers["Content-Type"] = "application/x-www-form-urlencoded"

            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=self.timeout_seconds
            ) as client:
                response = await client.post("/v2/auth/token", data=form, headers=headers)
                response.raise_for_status()
                payload = response.json()

            token = payload.get("access_token")
            if not token:
                raise RuntimeError("Token response did not include access_token")

            expires_in = int(payload.get("expires_in", 86400))
            self._cached_token = token
            self._cached_scope = payload.get("scope", requested_scope)
            self._expires_at_epoch = time.time() + expires_in

            payload["cached"] = False
            return payload

    async def get_access_token(self) -> str:
        token_data = await self.obtain_token()
        token = token_data.get("access_token")
        if not token:
            raise RuntimeError("No access token available")
        return token

    async def revoke_token(self, token: str | None = None) -> bool:
        token_to_revoke = token or self._cached_token
        if not token_to_revoke:
            raise RuntimeError("No token available to revoke")

        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout_seconds
        ) as client:
            response = await client.post(
                "/v2/auth/revoke", data={"token": token_to_revoke}, headers=headers
            )
            response.raise_for_status()

        if token_to_revoke == self._cached_token:
            self.clear_cache()
        return True

    def clear_cache(self) -> None:
        self._cached_token = None
        self._cached_scope = None
        self._expires_at_epoch = 0.0


def count_operations(spec: dict[str, Any]) -> int:
    total = 0
    for path_item in spec.get("paths", {}).values():
        for method in HTTP_METHODS:
            if method in path_item:
                total += 1
    return total


def load_spec(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(
            f"OpenAPI spec not found at {path}. Run "
            f"`python scripts/sync_personio_openapi.py --output {path}` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def filter_auth_paths(spec: dict[str, Any]) -> dict[str, Any]:
    filtered = copy.deepcopy(spec)
    for auth_path in AUTH_PATHS:
        filtered.get("paths", {}).pop(auth_path, None)
    return filtered


def build_server() -> FastMCP:
    base_url = os.environ.get("PERSONIO_BASE_URL", "https://api.personio.de")
    spec_path = Path(
        os.environ.get("PERSONIO_OPENAPI_PATH", "specs/personio-v2-openapi.json")
    )
    timeout_seconds = float(os.environ.get("PERSONIO_HTTP_TIMEOUT_SECONDS", "30"))
    refresh_buffer_seconds = int(
        os.environ.get("PERSONIO_TOKEN_REFRESH_BUFFER_SECONDS", "60")
    )

    client_id = get_env("PERSONIO_CLIENT_ID")
    client_secret = get_env("PERSONIO_CLIENT_SECRET")
    app_id = get_env("PERSONIO_APP_ID", "PERSONIO_MCP")
    partner_id = os.environ.get("PERSONIO_PARTNER_ID")
    default_scope = os.environ.get("PERSONIO_DEFAULT_SCOPE")
    allow_token_exposure = get_bool_env("PERSONIO_ALLOW_TOKEN_EXPOSURE", False)

    full_spec = load_spec(spec_path)
    runtime_spec = filter_auth_paths(full_spec)

    token_manager = PersonioTokenManager(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        default_scope=default_scope,
        app_id=app_id,
        partner_id=partner_id,
        timeout_seconds=timeout_seconds,
        refresh_buffer_seconds=refresh_buffer_seconds,
    )

    async def attach_personio_auth(request: httpx.Request) -> None:
        token = await token_manager.get_access_token()
        request.headers["Authorization"] = f"Bearer {token}"
        request.headers["X-Personio-App-ID"] = app_id
        if partner_id:
            request.headers["X-Personio-Partner-ID"] = partner_id

    client = httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout_seconds,
        event_hooks={"request": [attach_personio_auth]},
    )

    mcp = FastMCP.from_openapi(
        openapi_spec=runtime_spec,
        client=client,
        name="Personio MCP Server",
    )

    @mcp.tool(
        description=(
            "Return server metadata and endpoint coverage for this Personio MCP instance."
        )
    )
    def personio_mcp_info() -> dict[str, Any]:
        return {
            "name": "Personio MCP Server",
            "base_url": base_url,
            "spec_path": str(spec_path),
            "paths": len(full_spec.get("paths", {})),
            "operations_total": count_operations(full_spec),
            "operations_exposed_as_tools": count_operations(runtime_spec) + 3,
            "auth_paths_implemented_manually": sorted(AUTH_PATHS),
        }

    @mcp.tool(
        description=(
            "Obtain an OAuth2 access token using configured PERSONIO_CLIENT_ID and "
            "PERSONIO_CLIENT_SECRET. By default, the token value is masked."
        )
    )
    async def personio_auth_token(
        scope: str | None = None, include_access_token: bool = False
    ) -> dict[str, Any]:
        token_data = await token_manager.obtain_token(scope=scope, force_refresh=True)
        response: dict[str, Any] = {
            "token_type": token_data.get("token_type", "Bearer"),
            "expires_in": token_data.get("expires_in"),
            "scope": token_data.get("scope"),
            "cached": token_data.get("cached", False),
            "expires_at_epoch": token_manager.expires_at_epoch,
        }

        if include_access_token:
            if not allow_token_exposure:
                raise RuntimeError(
                    "Token exposure is disabled. Set PERSONIO_ALLOW_TOKEN_EXPOSURE=true "
                    "to allow returning raw access tokens."
                )
            response["access_token"] = token_data.get("access_token")
        else:
            response["access_token"] = "<hidden>"

        return response

    @mcp.tool(
        description=(
            "Revoke a Personio access token. If no token is provided, revokes the "
            "currently cached token."
        )
    )
    async def personio_auth_revoke(token: str | None = None) -> dict[str, Any]:
        revoked = await token_manager.revoke_token(token=token)
        return {"revoked": revoked, "used_cached_token": token is None}

    @mcp.tool(
        description=(
            "Clear local token cache. The next request will automatically fetch a new token."
        )
    )
    def personio_auth_clear_cache() -> dict[str, Any]:
        token_manager.clear_cache()
        return {"cache_cleared": True}

    @mcp.tool(
        description=(
            "List employees (Personio Persons API) with a simplified schema for "
            "MCP clients that are strict about complex OpenAPI-generated schemas."
        )
    )
    async def list_employees(
        limit: int = 10,
        cursor: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 50))}
        if cursor:
            params["cursor"] = cursor
        if email:
            params["email"] = email
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name

        response = await client.get("/v2/persons", params=params)
        response.raise_for_status()
        payload = response.json()
        people = payload.get("_data", [])
        meta = payload.get("_meta", {})

        return {
            "count": len(people),
            "people": people,
            "meta": meta,
        }

    @mcp.tool(
        description=(
            "Get a single employee (Personio Person) by ID using a simplified schema."
        )
    )
    async def get_employee(person_id: str) -> dict[str, Any]:
        response = await client.get(f"/v2/persons/{person_id}")
        response.raise_for_status()
        return response.json()

    return mcp


if __name__ == "__main__":
    server = build_server()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    print(f"Starting Personio MCP server on {host}:{port}")
    server.run(
        transport="http",
        host=host,
        port=port,
        stateless_http=True,
    )
