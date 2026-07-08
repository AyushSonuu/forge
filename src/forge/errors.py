"""Typed exception hierarchy for Forge.

Rules of thumb:

- ``ForgeError`` is the root; all Forge-raised exceptions inherit from it.
- Infrastructure failures (docker down, DB write failed) raise.
- Expected command failures (non-zero exit code, missing file in a read) do
  **not** raise from public APIs — they return structured results. The
  exceptions here are for infra/programmer errors.
"""
from __future__ import annotations


class ForgeError(Exception):
    """Base class for every Forge exception."""


class ConfigError(ForgeError):
    """Invalid configuration (bad path, missing image, etc.)."""


class NotFoundError(ForgeError):
    """A requested resource does not exist."""


class ConflictError(ForgeError):
    """State transition rejected (e.g. deleting a running workspace)."""


class WorkspaceError(ForgeError):
    """Workspace-layer failure (create, delete, path resolution)."""


class PathEscapeError(WorkspaceError):
    """Requested path resolved outside the workspace root — refused."""


class RuntimeDriverError(ForgeError):
    """Underlying runtime (docker, firecracker, ...) reported a failure."""


class ContainerStartError(RuntimeDriverError):
    """Container refused to start or exited before it became ready."""


class ExecTimeoutError(RuntimeDriverError):
    """Execution exceeded its wall-clock timeout."""


class PoolExhaustedError(ForgeError):
    """Pool has no capacity and the caller opted out of waiting."""


class PoolClosedError(ForgeError):
    """Pool has been shut down; new leases are rejected."""


class SnapshotError(ForgeError):
    """Snapshot create/restore failed."""


class ArtifactError(ForgeError):
    """Artifact export/read failed."""
