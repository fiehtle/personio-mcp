#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any


def post_mcp(url: str, payload: dict[str, Any], timeout: int = 40) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")

    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise RuntimeError("No data line returned by MCP endpoint")


def tool_call(url: str, name: str, arguments: dict[str, Any], rid: int) -> dict[str, Any]:
    return post_mcp(
        url,
        {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def structured_content(response: dict[str, Any]) -> dict[str, Any]:
    return response.get("result", {}).get("structuredContent", {}) or {}


def probe(url: str) -> dict[str, Any]:
    tools_response = post_mcp(
        url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    tools = tools_response["result"]["tools"]
    tool_names = {t["name"] for t in tools}

    fixtures: dict[str, str] = {}

    if "list_employees" in tool_names:
        res = tool_call(url, "list_employees", {"limit": 3}, 2)
        people = structured_content(res).get("people", [])
        if people:
            fixtures["person_id"] = people[0].get("id")

    if "list_projects" in tool_names:
        res = tool_call(url, "list_projects", {"limit": 3}, 3)
        data = structured_content(res).get("_data", [])
        if data:
            fixtures["project_id"] = data[0].get("id")

    if "list_absence_types" in tool_names:
        res = tool_call(url, "list_absence_types", {"limit": 3}, 4)
        data = structured_content(res).get("_data", [])
        if data:
            fixtures["absence_type_id"] = data[0].get("id")

    if "list_absence_periods" in tool_names:
        args: dict[str, Any] = {"limit": 3}
        if "person_id" in fixtures:
            args["person.id"] = fixtures["person_id"]
        res = tool_call(url, "list_absence_periods", args, 5)
        data = structured_content(res).get("result", {}).get("_data", [])
        if data:
            fixtures["absence_period_id"] = data[0].get("id")

    tested: list[dict[str, Any]] = []
    rid = 100

    for tool in sorted(tools, key=lambda t: t["name"]):
        name = tool["name"]
        if name.startswith(
            ("create_", "update_", "delete_", "add_", "remove_", "send_", "redeliver_")
        ):
            continue
        if name in {"personio_auth_revoke", "personio_auth_clear_cache"}:
            continue
        if not (
            name.startswith("list_")
            or name.startswith("get_")
            or name in {"personio_mcp_info", "personio_auth_token"}
        ):
            continue

        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = schema.get("required", []) if isinstance(schema, dict) else []
        args: dict[str, Any] = {}

        if "limit" in properties:
            args["limit"] = 3
        if "person_id" in properties and fixtures.get("person_id"):
            args["person_id"] = fixtures["person_id"]
        if "id" in properties and "id" in required:
            if "project" in name and fixtures.get("project_id"):
                args["id"] = fixtures["project_id"]
            elif "absence_period" in name and fixtures.get("absence_period_id"):
                args["id"] = fixtures["absence_period_id"]
            elif "absence_type" in name and fixtures.get("absence_type_id"):
                args["id"] = fixtures["absence_type_id"]
            elif fixtures.get("person_id"):
                args["id"] = fixtures["person_id"]
            else:
                args["id"] = "1"

        for req in required:
            if req not in args:
                args[req] = "1"

        rid += 1
        response = tool_call(url, name, args, rid)
        is_error = bool(response.get("result", {}).get("isError"))
        error_text = None
        if is_error:
            content = response.get("result", {}).get("content", [])
            if content:
                error_text = content[0].get("text")

        tested.append(
            {
                "tool": name,
                "args": args,
                "ok": not is_error,
                "error_text": error_text,
            }
        )

    ok = [x for x in tested if x["ok"]]
    failed = [x for x in tested if not x["ok"]]
    return {
        "fixtures": fixtures,
        "counts": {
            "total_tools": len(tools),
            "read_like_tested": len(tested),
            "ok": len(ok),
            "failed": len(failed),
        },
        "failed": failed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe live MCP tool health.")
    parser.add_argument(
        "--url",
        default="https://personio-mcp.onrender.com/mcp",
        help="MCP URL to probe.",
    )
    parser.add_argument(
        "--output",
        default="docs/mcp-tool-health.json",
        help="Output JSON report path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = probe(args.url)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(f"Wrote {args.output}")
    print(json.dumps(report["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

