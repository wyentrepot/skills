"""Verify the public API inventory from the workbench OpenAPI document.

The application OpenAPI output is the source of truth for route existence and
named request/response schemas.  This check deliberately builds the app with
inert FastAPI sub-applications: importing and inspecting the app never opens a
serial port, starts a listener, or performs a flash operation.

Examples::

    python scripts/verify_api_inventory.py --repo-root /01-workfile-ai/01-zzt/ZZT_SELF
    WORKBENCH_ROOT=/01-workfile-ai/01-zzt/ZZT_SELF python scripts/verify_api_inventory.py --json

The script resolves the workbench repository root in this order: ``--repo-root``
argument, ``WORKBENCH_ROOT`` environment variable, then a probe of known
candidate paths (WSL/Windows checkouts).  It exits non-zero when one of the
eight v2 facade routes or its named schemas drifts.  The JSON form is intended
for CI and documentation generation; the default form is a compact
human-readable inventory.  It only builds inert FastAPI sub-applications and
never opens a serial port, starts a listener, or performs a flash operation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


# 候选工作台仓库根（按存在性探测；也可用 --repo-root / WORKBENCH_ROOT 显式指定）。
_WORKBENCH_ROOT_CANDIDATES = (
    "/01-workfile-ai/01-zzt/ZZT_SELF",          # WSL 权威仓库
    "/mnt/d/019-wy-tool/ZZT_SELF",              # Windows D 盘（WSL 挂载）
    "/mnt/d/12-wy-share-workfile/01-zzt/ZZT_SELF",
    r"D:\019-wy-tool\ZZT_SELF",                 # Windows 原生路径
)


def _resolve_repo_root(cli_value: str | None) -> Path:
    raw = cli_value or os.environ.get("WORKBENCH_ROOT") or ""
    if raw:
        candidate = Path(raw).expanduser().resolve()
        if not (candidate / "apps" / "workbench").is_dir():
            raise SystemExit(
                f"[verify_api_inventory] WORKBENCH_ROOT 无效（缺少 apps/workbench）：{candidate}\n"
                f"请设置 WORKBENCH_ROOT 或 --repo-root 指向工作台仓库根。"
            )
        return candidate
    for raw_candidate in _WORKBENCH_ROOT_CANDIDATES:
        candidate = Path(raw_candidate)
        if (candidate / "apps" / "workbench").is_dir():
            return candidate
    raise SystemExit(
        "[verify_api_inventory] 未找到工作台仓库根。请用 --repo-root <WORKBENCH_ROOT> 或 "
        "WORKBENCH_ROOT 环境变量显式指定。"
    )


REPO_ROOT = _resolve_repo_root(None)
for _path in (REPO_ROOT, REPO_ROOT / "apps", REPO_ROOT / "libs"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


V2_PREFIX = "/api/ai/v2/"
V2_EXPECTED: dict[tuple[str, str], dict[str, str | None]] = {
    ("GET", "/api/ai/v2/capabilities"): {
        "request": None, "response": "CapabilitySnapshot", "capability": "capabilities.read",
    },
    ("POST", "/api/ai/v2/investigations"): {
        "request": "InvestigationRequest", "response": "JobEnvelope", "capability": "investigations.create",
    },
    ("POST", "/api/ai/v2/verification-runs"): {
        "request": "VerificationRunRequest", "response": "JobEnvelope", "capability": "verification_runs.create",
    },
    ("POST", "/api/ai/v2/module-actions"): {
        "request": "ModuleActionRequest", "response": "JobEnvelope", "capability": "module_actions.*",
    },
    ("POST", "/api/ai/v2/flash-jobs"): {
        "request": "FlashJobRequest", "response": "JobEnvelope", "capability": "flash_jobs.create",
    },
    ("GET", "/api/ai/v2/jobs/{job_id}"): {
        "request": None, "response": "JobEnvelope", "capability": "jobs.read",
    },
    ("POST", "/api/ai/v2/jobs/{job_id}/cancel"): {
        "request": None, "response": "JobEnvelope", "capability": "jobs.cancel",
    },
    ("GET", "/api/ai/v2/jobs/{job_id}/evidence"): {
        "request": None, "response": "EvidenceView", "capability": "jobs.evidence.read",
    },
}

REQUIRED_SCHEMAS = frozenset({
    "AccessContext", "Capability", "CapabilitySnapshot", "CorrelationKeys",
    "EvidenceItem", "EvidenceRef", "EvidenceView", "FlashJobRequest",
    "InvestigationRequest", "JobEnvelope", "ModuleActionRequest",
    "ObservationRequest", "ObservationTarget", "ObservationWindow",
    "ResourceAlias", "SourceHealth", "VerificationRunRequest",
})


def _inert_sub_app():
    """Return a mounted app whose state cannot access real hardware."""
    from fastapi import FastAPI

    sub_app = FastAPI()
    sub_app.state.module_serial_service = None
    sub_app.state.serial_service = None
    sub_app.state.log_service = None
    return sub_app


def build_openapi() -> dict[str, Any]:
    """Build the workbench OpenAPI document without starting hardware."""
    from workbench.app import create_workbench_app

    # Keep the app's persistence dependencies outside the repository.  The
    # OpenAPI build should have no observable workspace side effect.
    with tempfile.TemporaryDirectory(prefix="workbench-api-inventory-") as storage:
        app = create_workbench_app(
            module_log_factory=_inert_sub_app,
            listener_factory=_inert_sub_app,
            ai_storage_dir=Path(storage),
        )
        return app.openapi()


def _ref_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    ref = value.get("$ref")
    return str(ref).rsplit("/", 1)[-1] if ref else None


def _request_schema(operation: dict[str, Any]) -> str | None:
    body = operation.get("requestBody") or {}
    content = body.get("content") or {}
    for media_type in ("application/json", *sorted(content)):
        if media_type in content:
            return _ref_name((content[media_type] or {}).get("schema"))
    return None


def _response_schema(operation: dict[str, Any]) -> str | None:
    responses = operation.get("responses") or {}
    # 200 and 202 are the only successful response statuses in the v2 facade.
    for status in ("200", "202"):
        response = responses.get(status) or {}
        content = response.get("content") or {}
        schema = content.get("application/json", {}).get("schema")
        if schema:
            return _ref_name(schema)
    return None


def _tier(path: str) -> str:
    if path.startswith("/api/ai/v2/"):
        return "v2_task_facade"
    if path.startswith("/api/ai/v1/"):
        return "v1_expert_compat"
    if path in {"/api/health", "/api/platform-version"}:
        return "platform_probe"
    if path.startswith("/api/"):
        return "workbench_legacy_orchestration"
    return "static_or_root"


def verify(openapi: dict[str, Any]) -> dict[str, Any]:
    paths = openapi.get("paths") or {}
    schemas = ((openapi.get("components") or {}).get("schemas") or {})
    errors: list[str] = []
    v2_records: list[dict[str, Any]] = []

    for (method, path), expected in V2_EXPECTED.items():
        operation = (paths.get(path) or {}).get(method.lower())
        if operation is None:
            errors.append(f"missing v2 route: {method} {path}")
            continue
        request_schema = _request_schema(operation)
        response_schema = _response_schema(operation)
        if request_schema != expected["request"]:
            errors.append(
                f"{method} {path}: request schema {request_schema!r}, "
                f"expected {expected['request']!r}"
            )
        if response_schema != expected["response"]:
            errors.append(
                f"{method} {path}: response schema {response_schema!r}, "
                f"expected {expected['response']!r}"
            )
        v2_records.append({
            "method": method,
            "path": path,
            "tier": "v2_task_facade",
            "capability": expected["capability"],
            "request_schema": request_schema,
            "response_schema": response_schema,
        })

    actual_v2 = {
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith(V2_PREFIX)
        for method in operations
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }
    expected_v2 = set(V2_EXPECTED)
    for method, path in sorted(actual_v2 - expected_v2):
        errors.append(f"unexpected v2 route: {method} {path}")
    if len(actual_v2) != 8:
        errors.append(f"v2 route count is {len(actual_v2)}, expected 8")

    missing_schemas = sorted(REQUIRED_SCHEMAS - set(schemas))
    if missing_schemas:
        errors.append("missing named schemas: " + ", ".join(missing_schemas))

    all_routes: list[dict[str, Any]] = []
    for path in sorted(paths):
        for method, operation in sorted(paths[path].items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            all_routes.append({
                "method": method.upper(),
                "path": path,
                "tier": _tier(path),
                "tag": (operation.get("tags") or [None])[0],
            })

    tier_counts: dict[str, int] = {}
    for route in all_routes:
        tier_counts[route["tier"]] = tier_counts.get(route["tier"], 0) + 1

    try:
        from workbench.ai_auth import V2_CAPABILITY_SCOPES, V2_CAPABILITY_SOURCES

        capabilities = [
            {
                "name": name,
                "scopes": sorted(V2_CAPABILITY_SCOPES[name]),
                "sources": sorted(V2_CAPABILITY_SOURCES.get(name, ())),
            }
            for name in sorted(V2_CAPABILITY_SCOPES)
        ]
    except ImportError:
        capabilities = []
        errors.append("unable to import v2 capability mapping")

    # REQS-0022：listener 能力声明必须覆盖三个语义能力（`/api/ai/v1/listener/schema`）。
    listener_capabilities: dict[str, Any] | None = None
    try:
        from workbench.ai_operations import AIControlService

        schema = AIControlService.listener_schema()
        listener_capabilities = {
            "match_kinds": sorted(schema.get("match_kinds") or []),
            "trace_query": schema.get("trace_query") is not None,
            "minute_periods": schema.get("minute_periods") is not None,
            "evidence_l3_ref": schema.get("evidence_l3_ref") is not None,
        }
        for kind in ("trace_query", "minute_periods"):
            if kind not in (schema.get("match_kinds") or []):
                errors.append(f"listener schema missing match_kind: {kind}")
        for ability in ("trace_query", "minute_periods", "evidence_l3_ref"):
            if schema.get(ability) is None:
                errors.append(f"listener schema missing capability: {ability}")
    except ImportError:
        errors.append("unable to import listener schema")

    return {
        "ok": not errors,
        "errors": errors,
        "openapi_version": openapi.get("openapi"),
        "route_count": len(all_routes),
        "v2_route_count": len(actual_v2),
        "named_schema_count": len(schemas),
        "required_named_schemas": sorted(REQUIRED_SCHEMAS),
        "missing_named_schemas": missing_schemas,
        "v2_routes": v2_records,
        "ai_capabilities": capabilities,
        "listener_capabilities": listener_capabilities,
        "compatibility_tiers": tier_counts,
        "routes": all_routes,
    }


def _print_report(result: dict[str, Any]) -> None:
    state = "PASS" if result["ok"] else "FAIL"
    print(f"API inventory verification: {state}")
    print(f"OpenAPI {result['openapi_version']} · {result['route_count']} routes · {result['named_schema_count']} named schemas")
    print(f"v2 task facade: {result['v2_route_count']}/8 routes")
    print("\nAI capabilities:")
    for item in result["ai_capabilities"]:
        scopes = ", ".join(item["scopes"]) or "-"
        sources = ", ".join(item["sources"]) or "-"
        print(f"  {item['name']}: scopes=[{scopes}] sources=[{sources}]")
    listener_capabilities = result.get("listener_capabilities")
    if listener_capabilities:
        kinds = ", ".join(listener_capabilities["match_kinds"]) or "-"
        print(f"\nlistener capabilities: match_kinds=[{kinds}] "
              f"trace_query={listener_capabilities['trace_query']} "
              f"minute_periods={listener_capabilities['minute_periods']} "
              f"evidence_l3_ref={listener_capabilities['evidence_l3_ref']}")
    print("\nCompatibility tiers:")
    for tier, count in sorted(result["compatibility_tiers"].items()):
        print(f"  {tier}: {count}")
    print("\nv2 routes:")
    for route in result["v2_routes"]:
        print(f"  {route['method']:4} {route['path']} -> {route['response_schema']} [{route['capability']}]")
    if result["errors"]:
        print("\nErrors:")
        for error in result["errors"]:
            print(f"  - {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the complete machine-readable inventory")
    parser.add_argument("--repo-root", default=None, help="工作台仓库根（默认读 WORKBENCH_ROOT 或探测候选路径）")
    args = parser.parse_args(argv)
    # 提前解析 --repo-root，避免模块级探测用错根。
    global REPO_ROOT
    if args.repo_root:
        REPO_ROOT = _resolve_repo_root(args.repo_root)
        for _path in (REPO_ROOT, REPO_ROOT / "apps", REPO_ROOT / "libs"):
            if str(_path) not in sys.path:
                sys.path.insert(0, str(_path))
    result = verify(build_openapi())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_report(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":  # pragma: no cover - exercised by the CLI check
    raise SystemExit(main())
