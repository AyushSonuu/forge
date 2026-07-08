"""Smoke tests for the scaffold — ensures models import and are shaped correctly.

These give CI something concrete to run so branch 01 has a real green build,
not just an empty pytest run.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from forge import __version__
from forge.errors import ForgeError, PathEscapeError
from forge.models import (
    Execution,
    ExecutionResult,
    ForgeEvent,
    PoolConfig,
    PoolStats,
    ResourceLimits,
    RuntimeCapabilities,
    Snapshot,
    Workspace,
    WorkspaceSpec,
)


def test_version_is_declared() -> None:
    assert isinstance(__version__, str)
    assert __version__


def test_path_escape_error_is_forge_error() -> None:
    with pytest.raises(ForgeError):
        raise PathEscapeError("../../etc/passwd")


def test_workspace_spec_defaults() -> None:
    spec = WorkspaceSpec(image="python:3.13-slim")
    assert spec.runtime == "docker"
    assert spec.env == {}
    assert spec.resources == ResourceLimits()


def test_workspace_round_trips_json() -> None:
    ws = Workspace(
        id="ws_1",
        spec=WorkspaceSpec(image="python:3.13-slim"),
        status="ready",
    )
    reparsed = Workspace.model_validate_json(ws.model_dump_json())
    assert reparsed == ws


def test_execution_status_defaults_to_queued() -> None:
    ex = Execution(id="ex_1", workspace_id="ws_1", command=["echo", "hi"])
    assert ex.status == "queued"
    assert ex.exit_code is None
    assert ex.started_at is None


def test_execution_result_shape_matches_langchain_contract() -> None:
    # LangChain-compatible: single ``output`` string, integer exit_code,
    # non-raising. See docs/low-level-design.md#execution-result-mapping.
    result = ExecutionResult(
        execution_id="ex_1",
        output="hello\n",
        exit_code=0,
        duration_ms=42,
    )
    assert result.truncated is False
    assert result.output_path is None


def test_pool_config_defaults_are_reasonable() -> None:
    cfg = PoolConfig()
    assert cfg.min_idle >= 1
    assert cfg.max_size >= cfg.min_idle
    assert cfg.idle_ttl_seconds > 0
    assert cfg.exec_timeout_seconds > 0


def test_pool_stats_serialization() -> None:
    stats = PoolStats(image="python:3.13-slim", idle=2, in_use=1, total=3, max_size=8, min_idle=1)
    assert "python" in stats.model_dump_json()


def test_runtime_capabilities_defaults_are_docker_shaped() -> None:
    caps = RuntimeCapabilities()
    assert caps.isolation == "container"
    assert caps.supports_streaming_logs is True
    assert caps.gpu is False


def test_snapshot_defaults() -> None:
    snap = Snapshot(id="snap_1", workspace_id="ws_1")
    assert snap.format == "tar.zst"
    assert snap.size_bytes == 0


def test_forge_event_timestamp_is_utc() -> None:
    ev = ForgeEvent(kind="workspace.created", workspace_id="ws_1")
    assert isinstance(ev.ts, datetime)
    assert ev.ts.tzinfo is not None
    # sanity: at most a few seconds ago
    delta = (datetime.now(UTC) - ev.ts).total_seconds()
    assert 0 <= delta < 5
