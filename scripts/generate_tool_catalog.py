#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tool_naming import build_mcp_names

METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")


def summarize_description(text: str) -> str:
    if not text:
        return ""
    line = text.strip().split("\n")[0].strip()
    return line.replace("|", "\\|")


def load_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def operation_rows(spec: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    names = build_mcp_names(spec)
    for path, path_item in spec.get("paths", {}).items():
        for method in METHODS:
            operation = path_item.get(method)
            if not operation:
                continue
            operation_id = operation.get("operationId", "")
            tag = (operation.get("tags") or ["Other"])[0]
            rows.append(
                {
                    "domain": tag,
                    "tool_name": names.get(operation_id, operation_id),
                    "operation_id": operation_id,
                    "method_path": f"{method.upper()} {path}",
                    "purpose": (operation.get("summary") or "").replace("|", "\\|"),
                    "notes": summarize_description(operation.get("description", "")),
                }
            )
    rows.sort(key=lambda x: (x["domain"], x["tool_name"]))
    return rows


def render_markdown(rows: list[dict[str, str]]) -> str:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["domain"]].append(row)

    lines: list[str] = []
    lines.append("# Personio MCP Tool Catalog")
    lines.append("")
    lines.append("This catalog maps each Personio endpoint to assistant-friendly MCP tool names.")
    lines.append("")
    lines.append("## Recommended wrappers")
    lines.append("")
    lines.append("- `list_employees`: simplified employee listing for strict MCP clients.")
    lines.append("- `get_employee`: simplified fetch for a single employee by Person ID.")
    lines.append("- `personio_mcp_info`: server coverage and diagnostics.")
    lines.append("- `personio_auth_token`: validate token issuance (masked by default).")
    lines.append("- `personio_auth_revoke`: revoke current token if needed.")
    lines.append("")
    lines.append("## Endpoint mappings")
    lines.append("")

    for domain in sorted(grouped.keys()):
        lines.append(f"### {domain}")
        lines.append("")
        lines.append("| Tool | Endpoint | Purpose | Operation ID | Notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in grouped[domain]:
            lines.append(
                f"| `{row['tool_name']}` | `{row['method_path']}` | "
                f"{row['purpose']} | `{row['operation_id']}` | {row['notes']} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate markdown tool catalog from merged spec.")
    parser.add_argument(
        "--spec",
        default="specs/personio-v2-openapi.json",
        help="Path to merged OpenAPI spec.",
    )
    parser.add_argument(
        "--output",
        default="docs/personio-tool-catalog.md",
        help="Path to output markdown catalog.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = load_spec(Path(args.spec))
    rows = operation_rows(spec)
    markdown = render_markdown(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"Generated {out} for {len(rows)} operations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
