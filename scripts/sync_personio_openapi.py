#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REFERENCE_PAGE = "https://developer.personio.de/reference/get_v2-persons-id"
REGISTRY_URL_TEMPLATE = "https://dash.readme.com/api/v1/api-registry/{uuid}"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")
USER_AGENT = "personio-mcp-spec-sync/1.0"


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> dict[str, Any]:
    payload = fetch_text(url)
    return json.loads(payload)


def extract_registries(reference_page_html: str) -> list[dict[str, str]]:
    match = re.search(
        r'"apiRegistries":\[(.*?)\],"source":"readme"',
        reference_page_html,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError("Could not locate apiRegistries in Personio reference page")

    serialized = f"[{match.group(1)}]"
    serialized = serialized.encode("utf-8").decode("unicode_escape")
    registries = json.loads(serialized)

    parsed: list[dict[str, str]] = []
    for entry in registries:
        filename = entry.get("filename")
        uuid = entry.get("uuid")
        if not filename or not uuid:
            continue
        parsed.append({"filename": filename, "uuid": uuid})
    return parsed


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def merge_named_section(
    merged_section: dict[str, Any], incoming_section: dict[str, Any], section_name: str
) -> None:
    for item_name, item_value in incoming_section.items():
        if item_name not in merged_section:
            merged_section[item_name] = item_value
            continue
        # Personio specs define BearerAuth in multiple registries with minor
        # differences. Keeping the first one is sufficient for merged usage.
        if section_name == "components.securitySchemes" and item_name == "BearerAuth":
            continue
        if stable_json(merged_section[item_name]) != stable_json(item_value):
            raise ValueError(f"Conflicting {section_name}.{item_name} while merging specs")


def sanitize_namespace(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return normalized or "registry"


def rewrite_refs(value: Any, ref_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {k: rewrite_refs(v, ref_map) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite_refs(item, ref_map) for item in value]
    if isinstance(value, str):
        replacement = ref_map.get(value)
        if replacement:
            return replacement
        # Also rewrite nested refs like
        # "#/components/responses/Name/content/application~1json/schema".
        for old_prefix, new_prefix in ref_map.items():
            if value.startswith(old_prefix + "/"):
                return new_prefix + value[len(old_prefix) :]
        return value
    return value


def resolve_json_pointer(document: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported ref: {ref}")

    current: Any = document
    for raw_part in ref[2:].split("/"):
        part = unquote(raw_part).replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            index = int(part)
            current = current[index]
        else:
            raise KeyError(f"Reference part '{part}' not found in path '{ref}'")
    return current


def should_inline_ref(ref: str) -> bool:
    if not ref.startswith("#/"):
        return False
    parts = ref[2:].split("/")
    if not parts:
        return False
    if parts[0] == "paths":
        return True
    if parts[0] == "components" and len(parts) > 3:
        return True
    return False


def inline_selected_refs_in_node(
    node: Any, root: dict[str, Any], ref_stack: set[str] | None = None
) -> Any:
    if ref_stack is None:
        ref_stack = set()

    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str):
            ref = node["$ref"]
            if should_inline_ref(ref):
                if ref in ref_stack:
                    return node
                ref_stack.add(ref)
                target = copy.deepcopy(resolve_json_pointer(root, ref))
                # Merge any sibling keys, preserving local overrides.
                siblings = {k: v for k, v in node.items() if k != "$ref"}
                if siblings and isinstance(target, dict):
                    target.update(siblings)
                inlined = inline_selected_refs_in_node(target, root, ref_stack)
                ref_stack.remove(ref)
                return inlined
        return {k: inline_selected_refs_in_node(v, root, ref_stack) for k, v in node.items()}
    if isinstance(node, list):
        return [inline_selected_refs_in_node(item, root, ref_stack) for item in node]
    return node


def inline_path_refs(spec: dict[str, Any]) -> dict[str, Any]:
    return inline_selected_refs_in_node(spec, spec)


def decode_percent_encoded_refs(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: decode_percent_encoded_refs(v) for k, v in node.items()}
    if isinstance(node, list):
        return [decode_percent_encoded_refs(item) for item in node]
    if isinstance(node, str) and node.startswith("#/") and "%" in node:
        return unquote(node)
    return node


def namespace_components(spec: dict[str, Any], namespace: str) -> dict[str, Any]:
    transformed = copy.deepcopy(spec)
    components = transformed.get("components", {})
    if not isinstance(components, dict):
        return transformed

    ref_map: dict[str, str] = {}
    for section_name, items in components.items():
        if section_name == "securitySchemes" or not isinstance(items, dict):
            continue
        for item_name in items.keys():
            old_ref = f"#/components/{section_name}/{item_name}"
            new_ref = f"#/components/{section_name}/{namespace}__{item_name}"
            ref_map[old_ref] = new_ref

    transformed = rewrite_refs(transformed, ref_map)
    renamed_components = transformed.get("components", {})
    for section_name, items in list(renamed_components.items()):
        if section_name == "securitySchemes" or not isinstance(items, dict):
            continue
        renamed_components[section_name] = {
            f"{namespace}__{item_name}": item_value
            for item_name, item_value in items.items()
        }

    transformed = inline_path_refs(transformed)
    transformed = decode_percent_encoded_refs(transformed)
    return transformed


def merge_openapi_specs(specs: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    if not specs:
        raise ValueError("No specs provided")

    transformed_specs: list[dict[str, Any]] = []
    for filename, spec in specs:
        namespace = sanitize_namespace(filename)
        transformed_specs.append(namespace_components(spec, namespace))

    merged: dict[str, Any] = {
        "openapi": transformed_specs[0].get("openapi", "3.0.3"),
        "info": {
            "title": "Personio API v2 (Merged)",
            "version": "2.0.0",
            "description": "Merged OpenAPI spec generated from Personio Developer Hub registries.",
        },
        "servers": [{"url": "https://api.personio.de"}],
        "security": [{"BearerAuth": []}],
        "paths": {},
        "components": {},
    }

    for spec in transformed_specs:
        for path_key, path_item in spec.get("paths", {}).items():
            existing_path = merged["paths"].setdefault(path_key, {})
            for sub_key, sub_value in path_item.items():
                if sub_key not in existing_path:
                    existing_path[sub_key] = sub_value
                    continue
                if stable_json(existing_path[sub_key]) != stable_json(sub_value):
                    raise ValueError(f"Conflicting path operation for {path_key}.{sub_key}")

        for component_section, component_value in spec.get("components", {}).items():
            if not isinstance(component_value, dict):
                continue
            merged_components = merged["components"].setdefault(component_section, {})
            merge_named_section(
                merged_components, component_value, f"components.{component_section}"
            )

        # If any source spec defines security, keep it if merged has none.
        if not merged.get("security") and spec.get("security"):
            merged["security"] = spec["security"]

    assign_missing_operation_ids(merged)
    return merged


def operation_id_from_path(method: str, path: str) -> str:
    name = path.strip("/")
    name = re.sub(r"\{([^}]+)\}", r"by_\1", name)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return f"{method}_{name}" if name else method


def assign_missing_operation_ids(spec: dict[str, Any]) -> None:
    seen: set[str] = set()

    for path_key, path_item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not operation:
                continue

            operation_id = operation.get("operationId")
            if not operation_id:
                operation_id = operation_id_from_path(method, path_key)

            base = operation_id
            suffix = 2
            while operation_id in seen:
                operation_id = f"{base}_{suffix}"
                suffix += 1

            operation["operationId"] = operation_id
            seen.add(operation_id)


def count_operations(spec: dict[str, Any]) -> int:
    total = 0
    for path_item in spec.get("paths", {}).values():
        for method in HTTP_METHODS:
            if method in path_item:
                total += 1
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and merge Personio v2 OpenAPI registries into one spec."
    )
    parser.add_argument(
        "--reference-page",
        default=REFERENCE_PAGE,
        help="A Personio API reference page containing registry metadata.",
    )
    parser.add_argument(
        "--output",
        default="specs/personio-v2-openapi.json",
        help="Output path for merged OpenAPI JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        reference_html = fetch_text(args.reference_page)
        registries = extract_registries(reference_html)
        if not registries:
            raise RuntimeError("No API registries found")

        fetched_specs: list[tuple[str, dict[str, Any]]] = []
        for registry in registries:
            url = REGISTRY_URL_TEMPLATE.format(uuid=registry["uuid"])
            spec = fetch_json(url)
            fetched_specs.append((registry["filename"], spec))

        merged = merge_openapi_specs(fetched_specs)
        merged["x-personio-api-registries"] = registries

        output_path.write_text(
            json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        print(
            f"Synced {len(registries)} registries -> {output_path} "
            f"({len(merged.get('paths', {}))} paths, {count_operations(merged)} operations)"
        )
        return 0
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to sync Personio OpenAPI spec: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
