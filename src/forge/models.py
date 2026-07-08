"""Core domain models for Forge.

These are Pydantic v2 models so they round-trip cleanly through the HTTP layer.
The shapes match ``docs/mvp-design.md``. Anything runtime-facing (drivers,
pool internals) uses plain dataclasses (see driver/pool modules) to avoid
Pydantic overhead on hot paths.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


WorkspaceStatus = Literal["creating", "ready", "deleting", "deleted", "failed"]
ExecutionStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "timed_out"
]
EnvironmentStatus = Literal["creating", "running", "stopped", "failed"]
IsolationKind = Literal["process", "container", "microvm", "vm", "wasm"]


class ResourceLimits(BaseModel):
    """Best-effort resource caps applied per execution/environment."""

    model_config = ConfigDict(frozen=True)

    cpu: float | None = None  # cores; docker `nano_cpus = cpu * 1e9`
    memory: str | None = None  # "512Mi", "2Gi"
    disk: str | None = None  # advisory; not enforced by MVP docker driver


class WorkspaceSpec(BaseModel):
    """Declarative description of the environment an agent wants."""

    model_config = ConfigDict(frozen=True)

    image: str
    runtime: Literal["docker"] = "docker"
    working_dir: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    resources: ResourceLimits = Field(default_factory=ResourceLimits)


class Workspace(BaseModel):
    """A persistent, isolated workspace directory + spec."""

    id: str
    spec: WorkspaceSpec
    status: WorkspaceStatus
    name: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Environment (pooled container instance) — mostly internal
# ---------------------------------------------------------------------------


class Environment(BaseModel):
    """A running runtime instance (container) inside the pool.

    Environments are pool-owned in the MVP; each pooled container is one
    Environment. A workspace is *routed* onto an environment for the duration
    of an execution — it does not own one.
    """

    id: str
    image: str
    runtime: str = "docker"
    status: EnvironmentStatus = "creating"
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class Execution(BaseModel):
    id: str
    workspace_id: str
    environment_id: str | None = None
    command: list[str]
    shell: bool = False
    status: ExecutionStatus = "queued"
    exit_code: int | None = None
    truncated: bool = False
    output_path: str | None = None  # if output exceeded max_output_bytes
    started_at: datetime | None = None
    finished_at: datetime | None = None
    idempotency_key: str | None = None


class ExecutionResult(BaseModel):
    """LangChain-friendly result: stdout+stderr combined, non-raising."""

    execution_id: str
    output: str
    exit_code: int
    truncated: bool = False
    output_path: str | None = None
    duration_ms: int


class LogEvent(BaseModel):
    execution_id: str
    stream: Literal["stdout", "stderr"]
    ts: datetime = Field(default_factory=_utcnow)
    data: str


# ---------------------------------------------------------------------------
# Snapshots & Artifacts
# ---------------------------------------------------------------------------


class Snapshot(BaseModel):
    id: str
    workspace_id: str
    name: str | None = None
    format: Literal["tar.zst"] = "tar.zst"
    size_bytes: int = 0
    parent_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Artifact(BaseModel):
    id: str
    workspace_id: str
    path: str
    size_bytes: int
    content_type: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------


class PoolConfig(BaseModel):
    """Per-image sub-pool configuration.

    The daemon keeps a ``PoolConfig`` per image seen. New images inherit the
    ``default`` config unless overridden by the operator.
    """

    model_config = ConfigDict(frozen=True)

    image: str = "python:3.13-slim"
    min_idle: int = 1
    max_size: int = 8
    idle_ttl_seconds: int = 600
    exec_timeout_seconds: int = 120
    max_output_bytes: int = 100_000
    lease_wait_timeout_seconds: float = 30.0
    workspaces_mount: str = "/workspaces"  # inside-container mount point


class PoolStats(BaseModel):
    """Snapshot of pool state — reported by /pool/status."""

    image: str
    idle: int
    in_use: int
    total: int
    max_size: int
    min_idle: int
    total_leases: int = 0
    total_lease_wait_ms: int = 0
    total_health_kills: int = 0


class RuntimeCapabilities(BaseModel):
    """Advertised by every ``RuntimeDriver``.

    Callers dispatch on capabilities, not runtime name — this is what keeps
    the interface future-proof for Firecracker / K8s drivers in V2/V3.
    """

    model_config = ConfigDict(frozen=True)

    isolation: IsolationKind = "container"
    snapshots: bool = False
    pause_resume: bool = False
    network_control: bool = True
    resource_limits: bool = True
    hot_attach_volume: bool = False
    gpu: bool = False
    supports_streaming_logs: bool = True


# ---------------------------------------------------------------------------
# Request shapes (HTTP layer uses these directly)
# ---------------------------------------------------------------------------


class CreateWorkspaceRequest(BaseModel):
    spec: WorkspaceSpec
    name: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ExecRequest(BaseModel):
    command: list[str]
    shell: bool = False
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = None
    max_output_bytes: int | None = None
    idempotency_key: str | None = None


class FileWriteRequest(BaseModel):
    path: str
    content: str
    # base64 body support comes with the binary-upload endpoint; MVP is text.


class FileEditRequest(BaseModel):
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False


class FileReadResult(BaseModel):
    path: str
    content: str
    offset: int
    limit: int | None
    total_lines: int
    truncated: bool


class FileListEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: int
    modified_at: datetime


class SnapshotCreateRequest(BaseModel):
    name: str | None = None


class SnapshotRestoreRequest(BaseModel):
    name: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ArtifactExportRequest(BaseModel):
    path: str
    content_type: str | None = None


# ---------------------------------------------------------------------------
# Event bus payloads
# ---------------------------------------------------------------------------


class ForgeEvent(BaseModel):
    """Every state change flows through the bus as an event.

    Keeping this generic (a ``kind`` string + ``payload`` dict) sidesteps the
    proliferation of concrete event classes; consumers filter by ``kind``.
    """

    kind: str
    ts: datetime = Field(default_factory=_utcnow)
    workspace_id: str | None = None
    execution_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
