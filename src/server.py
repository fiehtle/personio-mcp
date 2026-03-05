#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import copy
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

try:
    from tool_naming import build_mcp_names
except ModuleNotFoundError:
    from src.tool_naming import build_mcp_names

AUTH_PATHS = {"/v2/auth/token", "/v2/auth/revoke"}
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")

# Tools that are either unavailable for this tenant (404 from Personio) or
# too unstable in generated schemas for assistant-facing use.
DEFAULT_DISABLED_TOOLS = {
    "list_recruiting_applications",
    "get_recruiting_application",
    "list_application_stage_transitions",
    "list_recruiting_candidates",
    "get_recruiting_candidate",
    "list_recruiting_categories",
    "get_recruiting_category",
    "list_recruiting_jobs",
    "get_recruiting_job",
    "list_workplaces",
    "list_cost_centers",
}

# Exclude unstable/unsupported endpoints at OpenAPI-import time so they never
# appear as MCP tools.
ROUTE_EXCLUDES = [
    RouteMap(methods=["GET"], pattern=r"^/v2/recruiting/.*", mcp_type=MCPType.EXCLUDE),
    RouteMap(methods=["GET"], pattern=r"^/v2/workplaces$", mcp_type=MCPType.EXCLUDE),
    RouteMap(methods=["GET"], pattern=r"^/v2/cost-centers$", mcp_type=MCPType.EXCLUDE),
    RouteMap(methods=["GET"], pattern=r"^/v2/persons$", mcp_type=MCPType.EXCLUDE),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/persons/\{person_id\}/employments$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(methods=["GET"], pattern=r"^/v2/legal-entities$", mcp_type=MCPType.EXCLUDE),
    RouteMap(methods=["GET"], pattern=r"^/v2/reports$", mcp_type=MCPType.EXCLUDE),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/reports/attributes$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(methods=["GET"], pattern=r"^/v2/compensations$", mcp_type=MCPType.EXCLUDE),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/attendance-periods/\{id\}$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/legal-entities/\{id\}$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/org-units/\{id\}$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/persons/\{person_id\}/employments/\{id\}$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/reports/\{id\}$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/webhooks/\{id\}$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/webhooks/\{id\}/activity$",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(
        methods=["GET"],
        pattern=r"^/v2/webhooks/\{id\}/events$",
        mcp_type=MCPType.EXCLUDE,
    ),
]


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
    disabled_tools_csv = os.environ.get("PERSONIO_DISABLED_TOOLS", "")
    recruiting_company_id = os.environ.get("PERSONIO_RECRUITING_COMPANY_ID")
    recruiting_api_key = os.environ.get("PERSONIO_RECRUITING_API_KEY")
    has_recruiting_auth = bool(recruiting_company_id and recruiting_api_key)

    full_spec = load_spec(spec_path)
    runtime_spec = filter_auth_paths(full_spec)
    mcp_names = build_mcp_names(runtime_spec)

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
        if request.url.path.startswith("/v1/recruiting/"):
            if not has_recruiting_auth:
                raise RuntimeError(
                    "Recruiting API credentials are not configured. Set "
                    "PERSONIO_RECRUITING_COMPANY_ID and PERSONIO_RECRUITING_API_KEY."
                )
            request.headers["Authorization"] = f"Bearer {recruiting_api_key}"
            request.headers["X-Company-Id"] = str(recruiting_company_id)
            request.headers["X-Personio-App-ID"] = app_id
            if partner_id:
                request.headers["X-Personio-Partner-ID"] = partner_id
            return

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
        mcp_names=mcp_names,
        route_maps=ROUTE_EXCLUDES,
    )

    disabled_tools = set(DEFAULT_DISABLED_TOOLS)
    if disabled_tools_csv.strip():
        disabled_tools.update(
            item.strip() for item in disabled_tools_csv.split(",") if item.strip()
        )
    for tool_name in sorted(disabled_tools):
        try:
            mcp.remove_tool(tool_name)
        except Exception:
            pass

    # Replace generated tools that frequently fail schema validation with
    # thin wrappers that return stable object shapes.
    for generated_name in [
        "list_persons",
        "list_person_employments",
        "list_legal_entities",
        "list_reports",
        "list_report_attributes",
        "list_compensations",
        "get_attendance_period",
        "get_legal_entity",
        "get_org_unit",
        "get_person_employment",
        "get_report",
        "get_webhook",
        "list_webhook_activity",
        "list_webhook_events",
    ]:
        try:
            mcp.remove_tool(generated_name)
        except Exception:
            pass

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
            "operations_exposed_as_tools": count_operations(runtime_spec) + 6,
            "auth_paths_implemented_manually": sorted(AUTH_PATHS),
            "disabled_tools": sorted(disabled_tools),
            "recruiting_auth_enabled": has_recruiting_auth,
            "recruiting_company_id_configured": bool(recruiting_company_id),
        }

    @mcp.tool(
        description=(
            "Show whether dedicated Personio Recruiting API credentials are configured "
            "for /v1/recruiting endpoints."
        )
    )
    def personio_recruiting_auth_info() -> dict[str, Any]:
        return {
            "enabled": has_recruiting_auth,
            "company_id": recruiting_company_id if recruiting_company_id else None,
            "api_key_configured": bool(recruiting_api_key),
            "required_env_vars": [
                "PERSONIO_RECRUITING_COMPANY_ID",
                "PERSONIO_RECRUITING_API_KEY",
            ],
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

    def _error_details(response: httpx.Response) -> dict[str, Any]:
        details: dict[str, Any] = {"status_code": response.status_code}
        try:
            details["body"] = response.json()
        except Exception:
            details["body"] = response.text
        return details

    def _require_recruiting_auth() -> tuple[str, str]:
        if not has_recruiting_auth or not recruiting_company_id or not recruiting_api_key:
            raise RuntimeError(
                "Recruiting API credentials are not configured. Set "
                "PERSONIO_RECRUITING_COMPANY_ID and PERSONIO_RECRUITING_API_KEY."
            )
        return recruiting_company_id, recruiting_api_key

    def _json_or_text(response: httpx.Response) -> Any:
        if not response.content:
            return {}
        try:
            return response.json()
        except Exception:
            return response.text

    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            data = payload.get("_data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        return []

    def _extract_single(payload: Any) -> Any:
        if isinstance(payload, dict) and "_data" in payload:
            return payload["_data"]
        return payload

    def _first_id_from_payload(payload: Any) -> str | None:
        for item in _extract_items(payload):
            if item.get("id") is not None:
                return str(item["id"])
        return None

    async def _resolve_first_resource_id(
        path: str, params: dict[str, Any] | None = None
    ) -> str | None:
        response = await client.get(path, params=params)
        response.raise_for_status()
        return _first_id_from_payload(response.json())

    async def _resolve_first_person_id() -> str | None:
        return await _resolve_first_resource_id("/v2/persons", {"limit": 1})

    async def _resolve_first_employment_id(person_id: str) -> str | None:
        return await _resolve_first_resource_id(
            f"/v2/persons/{person_id}/employments", {"limit": 1}
        )

    def _org_unit_from_employment(
        employment: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        for unit_type, field in (("department", "department"), ("team", "team")):
            value = employment.get(field)
            if isinstance(value, dict) and value.get("id") is not None:
                return str(value["id"]), unit_type
        for unit_type, field in (
            ("department", "department_id"),
            ("team", "team_id"),
            ("department", "department.id"),
            ("team", "team.id"),
        ):
            value = employment.get(field)
            if value is not None:
                return str(value), unit_type
        return None, None

    async def _resolve_org_unit_from_person(
        person_id: str | None = None,
    ) -> tuple[str | None, str | None]:
        resolved_person_id = person_id or await _resolve_first_person_id()
        if not resolved_person_id:
            return None, None

        response = await client.get(
            f"/v2/persons/{resolved_person_id}/employments", params={"limit": 1}
        )
        if response.status_code == 404:
            return None, None
        response.raise_for_status()

        items = _extract_items(response.json())
        if not items:
            return None, None
        return _org_unit_from_employment(items[0])

    async def _resolve_first_webhook_id() -> str | None:
        return await _resolve_first_resource_id("/v2/webhooks", {"limit": 1})

    @mcp.tool(
        name="get_attendance_period",
        description=(
            "Get an attendance period by ID. If no ID is provided, resolves the first "
            "matching period (optionally filtered by person_id)."
        ),
    )
    async def get_attendance_period(
        id: str | None = None, person_id: str | None = None
    ) -> dict[str, Any]:
        resolved_id = id
        if not resolved_id:
            params: dict[str, Any] = {"limit": 1}
            if person_id:
                params["person.id"] = person_id
            resolved_id = await _resolve_first_resource_id("/v2/attendance-periods", params)
            if not resolved_id:
                return {
                    "found": False,
                    "id": None,
                    "attendance_period": None,
                    "message": "No attendance periods found for the provided filters.",
                }

        response = await client.get(f"/v2/attendance-periods/{resolved_id}")
        if response.status_code in {400, 404}:
            return {
                "found": False,
                "id": resolved_id,
                "attendance_period": None,
                "error": _error_details(response),
            }
        response.raise_for_status()
        return {
            "found": True,
            "id": resolved_id,
            "attendance_period": _extract_single(response.json()),
        }

    @mcp.tool(
        name="get_legal_entity",
        description=(
            "Get a legal entity by ID. If no ID is provided, resolves the first legal entity."
        ),
    )
    async def get_legal_entity(id: str | None = None) -> dict[str, Any]:
        resolved_id = id or await _resolve_first_resource_id("/v2/legal-entities", {"limit": 1})
        if not resolved_id:
            return {
                "found": False,
                "id": None,
                "legal_entity": None,
                "message": "No legal entities found.",
            }

        response = await client.get(f"/v2/legal-entities/{resolved_id}")
        if response.status_code == 404:
            return {
                "found": False,
                "id": resolved_id,
                "legal_entity": None,
                "error": _error_details(response),
            }
        response.raise_for_status()
        return {
            "found": True,
            "id": resolved_id,
            "legal_entity": _extract_single(response.json()),
        }

    @mcp.tool(
        name="get_org_unit",
        description=(
            "Get an org unit by ID and type (team/department). If no ID is provided, "
            "tries to infer one from the first available employment."
        ),
    )
    async def get_org_unit(
        id: str | None = None,
        type: str | None = None,
        include_parent_chain: bool = False,
        person_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_id = str(id) if id else None
        inferred_type: str | None = None
        if not resolved_id:
            resolved_id, inferred_type = await _resolve_org_unit_from_person(person_id=person_id)
            if not resolved_id:
                return {
                    "found": False,
                    "id": None,
                    "org_unit": None,
                    "message": (
                        "No org unit ID could be inferred. Provide an org unit ID and type "
                        "(team or department)."
                    ),
                }

        requested_type = (type or "").strip().lower()
        if requested_type in {"team", "department"}:
            candidate_types = [requested_type]
        elif inferred_type in {"team", "department"}:
            candidate_types = [inferred_type] + [
                item for item in ("department", "team") if item != inferred_type
            ]
        else:
            candidate_types = ["department", "team"]

        errors: list[dict[str, Any]] = []
        for unit_type in candidate_types:
            params: dict[str, Any] = {"type": unit_type}
            if include_parent_chain:
                params["include_parent_chain"] = "true"

            response = await client.get(f"/v2/org-units/{resolved_id}", params=params)
            if response.status_code == 200:
                return {
                    "found": True,
                    "id": resolved_id,
                    "type": unit_type,
                    "org_unit": _extract_single(response.json()),
                }
            if response.status_code in {400, 404}:
                errors.append({"type": unit_type, **_error_details(response)})
                continue
            if response.status_code == 412:
                return {
                    "found": False,
                    "id": resolved_id,
                    "type": unit_type,
                    "org_unit": None,
                    "error": _error_details(response),
                }
            response.raise_for_status()

        return {
            "found": False,
            "id": resolved_id,
            "type": requested_type or inferred_type,
            "org_unit": None,
            "tried_types": candidate_types,
            "errors": errors,
        }

    @mcp.tool(
        name="get_person_employment",
        description=(
            "Get an employment by person_id and employment id. If either is missing, "
            "the tool resolves the first available value."
        ),
    )
    async def get_person_employment(
        person_id: str | None = None,
        id: str | None = None,
    ) -> dict[str, Any]:
        resolved_person_id = person_id or await _resolve_first_person_id()
        if not resolved_person_id:
            return {
                "found": False,
                "person_id": None,
                "id": None,
                "employment": None,
                "message": "No persons found in this account.",
            }

        resolved_id = id or await _resolve_first_employment_id(resolved_person_id)
        if not resolved_id:
            return {
                "found": False,
                "person_id": resolved_person_id,
                "id": None,
                "employment": None,
                "message": "No employments found for the selected person.",
            }

        response = await client.get(
            f"/v2/persons/{resolved_person_id}/employments/{resolved_id}"
        )
        if response.status_code == 404:
            return {
                "found": False,
                "person_id": resolved_person_id,
                "id": resolved_id,
                "employment": None,
                "error": _error_details(response),
            }
        response.raise_for_status()
        return {
            "found": True,
            "person_id": resolved_person_id,
            "id": resolved_id,
            "employment": _extract_single(response.json()),
        }

    @mcp.tool(
        name="get_report",
        description=(
            "Get a report by ID. If no ID is provided, resolves the first report."
        ),
    )
    async def get_report(
        id: str | None = None,
        locale: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        resolved_id = id or await _resolve_first_resource_id("/v2/reports", {"limit": 1})
        if not resolved_id:
            return {
                "found": False,
                "id": None,
                "report": None,
                "message": "No reports found.",
            }

        params: dict[str, Any] = {}
        if locale:
            params["locale"] = locale
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit

        response = await client.get(f"/v2/reports/{resolved_id}", params=params)
        if response.status_code in {400, 404}:
            return {
                "found": False,
                "id": resolved_id,
                "report": None,
                "error": _error_details(response),
            }
        response.raise_for_status()
        return {"found": True, "id": resolved_id, "report": _extract_single(response.json())}

    @mcp.tool(
        name="get_webhook",
        description=(
            "Get a webhook by ID. If no ID is provided, resolves the first webhook."
        ),
    )
    async def get_webhook(id: str | None = None) -> dict[str, Any]:
        resolved_id = id or await _resolve_first_webhook_id()
        if not resolved_id:
            return {
                "found": False,
                "id": None,
                "webhook": None,
                "message": "No webhooks are currently configured.",
            }

        response = await client.get(f"/v2/webhooks/{resolved_id}")
        if response.status_code in {403, 404}:
            return {
                "found": False,
                "id": resolved_id,
                "webhook": None,
                "error": _error_details(response),
            }
        response.raise_for_status()
        return {"found": True, "id": resolved_id, "webhook": _extract_single(response.json())}

    @mcp.tool(
        name="list_webhook_activity",
        description=(
            "List delivery activity for a webhook. If no webhook ID is provided, "
            "uses the first available webhook."
        ),
    )
    async def list_webhook_activity(
        id: str | None = None,
        completed_at_gte: str | None = None,
        completed_at_lte: str | None = None,
        event_name: str | None = None,
        is_delivered: bool | None = None,
        redelivery_id: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        resolved_id = id or await _resolve_first_webhook_id()
        if not resolved_id:
            return {
                "found": False,
                "webhook_id": None,
                "count": 0,
                "activities": [],
                "message": "No webhooks are currently configured.",
            }

        params: dict[str, Any] = {"limit": max(1, min(limit, 200))}
        if completed_at_gte:
            params["completed_at.gte"] = completed_at_gte
        if completed_at_lte:
            params["completed_at.lte"] = completed_at_lte
        if event_name:
            params["event_name"] = event_name
        if is_delivered is not None:
            params["is_delivered"] = is_delivered
        if redelivery_id:
            params["redelivery_id"] = redelivery_id
        if cursor:
            params["cursor"] = cursor

        response = await client.get(f"/v2/webhooks/{resolved_id}/activity", params=params)
        if response.status_code in {403, 404, 422}:
            return {
                "found": False,
                "webhook_id": resolved_id,
                "count": 0,
                "activities": [],
                "error": _error_details(response),
            }
        response.raise_for_status()

        payload = response.json()
        items = _extract_items(payload)
        return {
            "found": True,
            "webhook_id": resolved_id,
            "count": len(items),
            "activities": items,
            "meta": payload.get("_meta", {}) if isinstance(payload, dict) else {},
        }

    @mcp.tool(
        name="list_webhook_events",
        description=(
            "List events for a webhook. If no webhook ID is provided, "
            "uses the first available webhook."
        ),
    )
    async def list_webhook_events(
        id: str | None = None,
        occurred_at_gte: str | None = None,
        occurred_at_lte: str | None = None,
        event_name: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        resolved_id = id or await _resolve_first_webhook_id()
        if not resolved_id:
            return {
                "found": False,
                "webhook_id": None,
                "count": 0,
                "events": [],
                "message": "No webhooks are currently configured.",
            }

        params: dict[str, Any] = {"limit": max(1, min(limit, 200))}
        if occurred_at_gte:
            params["occurred_at.gte"] = occurred_at_gte
        if occurred_at_lte:
            params["occurred_at.lte"] = occurred_at_lte
        if event_name:
            params["event_name"] = event_name
        if cursor:
            params["cursor"] = cursor

        response = await client.get(f"/v2/webhooks/{resolved_id}/events", params=params)
        if response.status_code in {403, 404, 422}:
            return {
                "found": False,
                "webhook_id": resolved_id,
                "count": 0,
                "events": [],
                "error": _error_details(response),
            }
        response.raise_for_status()

        payload = response.json()
        items = _extract_items(payload)
        return {
            "found": True,
            "webhook_id": resolved_id,
            "count": len(items),
            "events": items,
            "meta": payload.get("_meta", {}) if isinstance(payload, dict) else {},
        }

    @mcp.tool(
        name="list_persons",
        description="List persons with a stable output schema.",
    )
    async def list_persons_wrapper(
        limit: int = 10,
        cursor: str | None = None,
        id: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        preferred_name: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 50))}
        if cursor:
            params["cursor"] = cursor
        if id:
            params["id"] = id
        if email:
            params["email"] = email
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if preferred_name:
            params["preferred_name"] = preferred_name
        if created_at:
            params["created_at"] = created_at
        if updated_at:
            params["updated_at"] = updated_at

        response = await client.get("/v2/persons", params=params)
        response.raise_for_status()
        payload = response.json()
        people = payload.get("_data", [])
        return {"count": len(people), "people": people, "meta": payload.get("_meta", {})}

    @mcp.tool(
        name="list_person_employments",
        description="List employments for a person with a stable output schema.",
    )
    async def list_person_employments_wrapper(
        person_id: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if cursor:
            params["cursor"] = cursor

        response = await client.get(f"/v2/persons/{person_id}/employments", params=params)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("_data", [])
        return {"count": len(items), "employments": items, "meta": payload.get("_meta", {})}

    @mcp.tool(
        name="list_legal_entities",
        description="List legal entities with a stable output schema.",
    )
    async def list_legal_entities_wrapper(
        limit: int = 50,
        cursor: str | None = None,
        id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if cursor:
            params["cursor"] = cursor
        if id:
            params["id"] = id
        if name:
            params["name"] = name

        response = await client.get("/v2/legal-entities", params=params)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("_data", [])
        return {"count": len(items), "legal_entities": items, "meta": payload.get("_meta", {})}

    @mcp.tool(
        name="list_reports",
        description="List reports with a stable output schema.",
    )
    async def list_reports_wrapper(limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if cursor:
            params["cursor"] = cursor

        response = await client.get("/v2/reports", params=params)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("_data", [])
        return {"count": len(items), "reports": items, "meta": payload.get("_meta", {})}

    @mcp.tool(
        name="list_report_attributes",
        description="List report attributes with a stable output schema.",
    )
    async def list_report_attributes_wrapper() -> dict[str, Any]:
        response = await client.get("/v2/reports/attributes")
        response.raise_for_status()
        payload = response.json()
        items = payload.get("_data", [])
        return {"count": len(items), "attributes": items, "meta": payload.get("_meta", {})}

    @mcp.tool(
        name="list_compensations",
        description="List compensations with a stable output schema.",
    )
    async def list_compensations_wrapper(
        start_date: str | None = None,
        end_date: str | None = None,
        person_id: str | None = None,
        legal_entity_id: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if person_id:
            params["person.id"] = person_id
        if legal_entity_id:
            params["legal_entity.id"] = legal_entity_id
        if cursor:
            params["cursor"] = cursor

        response = await client.get("/v2/compensations", params=params)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("_data", [])
        return {"count": len(items), "compensations": items, "meta": payload.get("_meta", {})}

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

    @mcp.tool(
        description=(
            "Create a recruiting application via Personio Recruiting API v1 "
            "(/v1/recruiting/applications) using dedicated recruiting credentials."
        )
    )
    async def recruiting_create_application(payload: dict[str, Any]) -> dict[str, Any]:
        _require_recruiting_auth()

        response = await client.post("/v1/recruiting/applications", json=payload)
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": _json_or_text(response),
            }

        return {
            "ok": True,
            "status_code": response.status_code,
            "result": _json_or_text(response),
        }

    @mcp.tool(
        description=(
            "Upload a recruiting document via Personio Recruiting API v1 "
            "(/v1/recruiting/applications/documents). Returns document identifier "
            "that can be attached to an application payload."
        )
    )
    async def recruiting_upload_application_document(
        filename: str,
        content_base64: str,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        _require_recruiting_auth()

        try:
            file_bytes = base64.b64decode(content_base64, validate=True)
        except Exception as exc:
            raise RuntimeError("content_base64 must be valid base64 data.") from exc

        files = {"file": (filename, file_bytes, content_type)}
        response = await client.post("/v1/recruiting/applications/documents", files=files)
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": _json_or_text(response),
            }

        return {
            "ok": True,
            "status_code": response.status_code,
            "result": _json_or_text(response),
        }

    @mcp.tool(
        description=(
            "Safe connectivity probe for Recruiting API credentials. Sends an invalid "
            "payload to /v1/recruiting/applications and reports auth vs validation behavior."
        )
    )
    async def recruiting_probe() -> dict[str, Any]:
        _require_recruiting_auth()

        response = await client.post("/v1/recruiting/applications", json={})
        result = {
            "status_code": response.status_code,
            "response": _json_or_text(response),
            "interpretation": (
                "401/403 usually means credential or permission issue. "
                "400/422 usually means auth succeeded but payload is invalid."
            ),
        }
        if response.status_code < 400:
            result["interpretation"] = (
                "Request unexpectedly succeeded with empty payload; credentials are valid."
            )
        return result

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
