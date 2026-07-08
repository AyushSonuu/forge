# MVP Implementation Plan

## Purpose

This document turns the Forge MVP into small, independently implementable features. Each feature includes scope, rollout order, high-level design (HLD), low-level design (LLD), acceptance criteria, dependencies, and suggested branch ownership so parallel agents or contributors can work without stepping on each other.

## MVP Goal

Build a Python-first Forge MVP that lets a LangChain Deep Agent use a Forge-backed sandbox directly while Forge provides persistent workspace files, Docker-backed command execution, file transfer, snapshots, artifacts, and basic cleanup.

## Rollout Sequence

The MVP should be delivered in thin vertical slices:

1. Repository and Python package foundation.
2. Core domain models and errors.
3. Local workspace store.
4. Docker runtime driver.
5. File service and workspace filesystem operations.
6. Execution service with log capture and timeouts.
7. Snapshot and restore.
8. Artifact export and download.
9. LangChain `ForgeSandbox` adapter.
10. CLI for manual use and debugging.
11. TTL cleanup and metadata indexes.
12. Integration tests and example agent.

Features 1 and 2 should happen first. After that, features 3, 4, and 5 can proceed in parallel. The LangChain adapter should start after the file and execution contracts are stable enough to mock.

## Parallel Branch Strategy

Use one branch per feature:

```text
feature/01-python-foundation
feature/02-core-models
feature/03-local-workspace-store
feature/04-docker-runtime-driver
feature/05-file-service
feature/06-execution-service
feature/07-snapshot-restore
feature/08-artifacts
feature/09-langchain-adapter
feature/10-cli
feature/11-ttl-cleanup
feature/12-integration-tests
```

Each branch should modify only its owned files when possible. Shared interfaces should be added early in feature 2 so later feature branches depend on stable contracts instead of editing the same files repeatedly.

## Feature 01 — Python Project Foundation

### Goal

Create the installable Python package skeleton and development tooling.

### Owned Paths

```text
pyproject.toml
README.md
forge/__init__.py
forge/py.typed
tests/__init__.py
```

### HLD

Forge should be importable as a Python package and expose a small public surface. The foundation should not implement runtime behavior; it should only define packaging, formatting, typing, and test commands.

### LLD

- Use `pyproject.toml` as the single source of package metadata.
- Package name: `forge-runtime` if `forge` is unavailable on package indexes; import package remains `forge`.
- Python target: 3.11+.
- Include typing marker `forge/py.typed`.
- Add development dependencies for `pytest`, `pytest-asyncio`, `ruff`, and `mypy` or `pyright`.
- Export package version from `forge.__init__`.

### Acceptance Criteria

- `python -m pytest` runs successfully with at least one placeholder test.
- `python -c "import forge"` succeeds.
- Formatting and lint commands are documented.

### Dependencies

None.

## Feature 02 — Core Domain Models and Protocols

### Goal

Define the stable MVP contracts used by all other features.

### Owned Paths

```text
forge/models.py
forge/errors.py
forge/protocols.py
forge/events.py
tests/test_models.py
```

### HLD

The core should expose Python dataclasses and protocols for workspaces, executions, snapshots, artifacts, runtime drivers, workspace stores, artifact stores, and event publishing. These contracts should be concrete enough for MVP implementation but small enough to support Firecracker and remote storage later.

### LLD

Define:

- `Workspace`
- `WorkspaceSpec`
- `ResourceLimits`
- `Environment`
- `Execution`
- `ExecutionResult`
- `Snapshot`
- `Artifact`
- `RuntimeCapabilities`
- `RuntimeDriver` protocol
- `WorkspaceStore` protocol
- `ArtifactStore` protocol
- `EventBus` protocol
- Forge exception hierarchy

Rules:

- Use `dataclass(frozen=True)` for immutable records.
- Use `Literal` for known status strings.
- Use explicit `datetime` fields for lifecycle records.
- Keep protocol methods async where I/O is expected.

### Acceptance Criteria

- Model tests cover construction and serialization helpers.
- Protocols can be type-checked with simple fake implementations.
- No Docker, LangChain, or storage-specific imports exist in core model files.

### Dependencies

Feature 01.

## Feature 03 — Local Workspace Store

### Goal

Implement local persistent workspace directories and metadata storage.

### Owned Paths

```text
forge/workspaces.py
forge/storage/local.py
tests/test_local_workspace_store.py
```

### HLD

The local workspace store maps each workspace ID to a directory on disk and a metadata record. It is the MVP persistence layer and should be simple, deterministic, and easy to inspect during debugging.

### LLD

Directory layout:

```text
.forge/
  workspaces/
    <workspace-id>/
      workspace/
      metadata.json
  snapshots/
  artifacts/
  indexes/
```

Implement:

- `create(request) -> Workspace`
- `get(workspace_id) -> Workspace`
- `list() -> list[Workspace]`
- `delete(workspace_id) -> None`
- `path(workspace_id) -> Path`
- metadata index by ID
- optional lookup by scope metadata for LangChain reuse

### Acceptance Criteria

- Creating a workspace creates a directory and metadata file.
- Deleting a workspace removes workspace data or marks it deleted based on policy.
- Listing workspaces returns persisted metadata after process restart.
- Scope metadata can find existing thread-scoped workspaces.

### Dependencies

Features 01 and 02.

## Feature 04 — Docker Runtime Driver

### Goal

Run commands inside Docker containers with the workspace mounted into the container.

### Owned Paths

```text
forge/runtime/docker.py
tests/test_docker_runtime.py
```

### HLD

The Docker runtime driver provides the MVP execution backend. It should mount the workspace directory into a container, apply resource limits where possible, run commands, capture output, enforce timeout, and return structured execution results.

### LLD

Implementation options:

- Prefer Docker CLI subprocess for MVP simplicity.
- Keep a thin internal adapter so later versions can switch to Docker SDK if needed.
- Mount workspace path to `/workspace`.
- Default working directory: `/workspace`.
- Support environment variables from `WorkspaceSpec`.
- Support network mode option.
- Support CPU and memory flags where configured.
- Use `asyncio.create_subprocess_exec` for command execution.

### Acceptance Criteria

- Can execute `python -c "print('hello')"` in `python:3.13`.
- Captures stdout, stderr, and exit code.
- Enforces timeout.
- Does not mount the host Docker socket.
- Leaves modified files in the workspace directory.

### Dependencies

Features 01, 02, and 03.

## Feature 05 — File Service

### Goal

Expose workspace file operations required by the SDK, CLI, and LangChain adapter.

### Owned Paths

```text
forge/files.py
tests/test_files.py
```

### HLD

The file service provides safe relative-path operations inside a workspace. It should prevent path traversal and expose the operations needed by LangChain Deep Agents filesystem tools.

### LLD

Implement:

- `ls(path='.')`
- `read(path, offset=0, limit=None)`
- `write(path, content, create_parents=True)`
- `edit(path, old_string, new_string, replace_all=False)`
- `glob(pattern, path='.')`
- `grep(pattern, path='.', glob_pattern=None)`
- `delete(path)`
- `upload_files(files)`
- `download_files(paths)`

Security rules:

- Resolve paths relative to workspace root.
- Reject absolute paths unless explicitly allowed later.
- Reject `..` traversal outside the workspace.
- Limit read output size.

### Acceptance Criteria

- File operations work across process restarts.
- Path traversal attempts fail.
- Upload/download supports multiple files.
- `grep` and `glob` match expected LangChain-style use cases.

### Dependencies

Features 01, 02, and 03.

## Feature 06 — Execution Service

### Goal

Provide a higher-level service for command execution with logs, result handling, and output truncation.

### Owned Paths

```text
forge/executions.py
tests/test_executions.py
```

### HLD

The execution service wraps the runtime driver and normalizes command results for Forge SDK, CLI, and LangChain. It should expose both structured stdout/stderr and a combined output mode for LangChain compatibility.

### LLD

Implement:

- `exec(workspace_id, command, shell=False, timeout=None)`
- execution metadata creation
- stdout/stderr capture
- combined output generation
- max output bytes truncation
- full output spill to workspace file when truncated
- cancellation hook placeholder

### Acceptance Criteria

- Successful commands return exit code 0.
- Failing commands return non-zero exit code without raising normal command errors.
- Timeout returns `timed_out` status.
- Long output is truncated and full output is saved to a file.

### Dependencies

Features 02, 03, and 04.

## Feature 07 — Snapshot and Restore

### Goal

Support archive-based workspace snapshots and restoration.

### Owned Paths

```text
forge/snapshots.py
tests/test_snapshots.py
```

### HLD

Snapshots provide a simple MVP state checkpoint. Archive-based snapshots are not the final scalable design, but they are easy to understand and enough for V1.

### LLD

Implement:

- `create_snapshot(workspace_id, name=None)`
- `restore_snapshot(snapshot_id, name=None)`
- tar archive creation
- optional zstd compression if dependency is available; fallback to gzip or tar for MVP
- snapshot metadata record
- checksum calculation

### Acceptance Criteria

- Snapshot captures workspace files.
- Restore creates a new workspace with the captured files.
- Metadata includes source workspace ID, created time, format, and size.
- Corrupt snapshot restore fails with a clear error.

### Dependencies

Features 02 and 03.

## Feature 08 — Artifact Store

### Goal

Export generated files as durable artifacts.

### Owned Paths

```text
forge/artifacts.py
tests/test_artifacts.py
```

### HLD

Artifacts are user-facing outputs from a workspace. They should be separate from snapshots because artifacts are intended for download, display, or integration with other systems.

### LLD

Implement:

- `export_file(workspace_id, path) -> Artifact`
- `get(artifact_id) -> Artifact`
- `read(artifact_id) -> AsyncIterator[bytes]`
- artifact metadata records
- content type detection best effort

### Acceptance Criteria

- Can export a file from a workspace.
- Can read exported artifact bytes.
- Missing files return clear errors.
- Artifact metadata persists after process restart.

### Dependencies

Features 02, 03, and 05.

## Feature 09 — LangChain ForgeSandbox Adapter

### Goal

Allow Forge to be used directly as a LangChain Deep Agents sandbox backend.

### Owned Paths

```text
forge/langchain/__init__.py
forge/langchain/sandbox.py
forge/langchain/scope.py
tests/test_langchain_sandbox.py
examples/langchain_deep_agent.py
```

### HLD

`ForgeSandbox` adapts LangChain Deep Agents backend calls to Forge workspace, file, and execution services. The agent remains outside Forge; tool calls delegate filesystem and shell operations into the Forge workspace.

### LLD

Implement:

- `ForgeSandbox.from_thread(...)`
- `ForgeSandbox.from_assistant(...)`
- scope resolution by metadata
- `execute(command: str)` mapping to execution service with `shell=True`
- filesystem method forwarding to file service
- `upload_files(...)`
- `download_files(...)`
- output truncation behavior compatible with execution service
- TTL metadata attachment

### Acceptance Criteria

- `ForgeSandbox` can be passed to `create_deep_agent(..., backend=backend)`.
- Agent can write, read, edit, glob, grep, and delete files through backend tools.
- Agent can execute shell commands and receive output plus exit code.
- Thread-scoped workspace is reused across invocations.
- Secrets are not injected by default.

### Dependencies

Features 02, 03, 05, and 06.

## Feature 10 — CLI

### Goal

Provide a developer-friendly CLI for local debugging and manual workflows.

### Owned Paths

```text
forge/cli.py
tests/test_cli.py
```

### HLD

The CLI should expose the same core operations as the SDK so contributors can debug workspaces without writing Python code.

### LLD

Commands:

```bash
forge workspace create --name demo --image python:3.13
forge workspace list
forge exec demo -- python -c "print('hello')"
forge files read demo main.py
forge files write demo main.py ./main.py
forge snapshot create demo
forge snapshot restore <snapshot-id>
forge artifact export demo ./report.json
forge cleanup run
```

Use `argparse` for MVP unless a richer CLI framework is justified later.

### Acceptance Criteria

- CLI can create workspace, run command, read/write file, create snapshot, restore snapshot, and export artifact.
- CLI exits non-zero for infrastructure errors.
- Command failures report exit code without crashing the CLI.

### Dependencies

Features 03, 05, 06, 07, and 08.

## Feature 11 — TTL Cleanup and Metadata Indexes

### Goal

Clean up idle workspaces and support fast lookup by scope metadata.

### Owned Paths

```text
forge/cleanup.py
forge/indexes.py
tests/test_cleanup.py
tests/test_indexes.py
```

### HLD

LangChain-style usage creates many thread-scoped workspaces. Forge needs TTL cleanup to avoid unbounded disk growth and indexes to reuse workspaces efficiently.

### LLD

Implement:

- workspace metadata indexes by ID, name, thread ID, assistant ID, user ID,
- `last_used_at` updates on file and execution operations,
- `idle_ttl_seconds` metadata,
- cleanup dry-run mode,
- cleanup delete/archive modes,
- optional maximum workspace count or disk usage guardrails.

### Acceptance Criteria

- Expired workspaces are detected.
- Cleanup dry run reports what would be removed.
- Cleanup delete mode removes expired workspace files and metadata.
- Scope lookup remains correct after cleanup.

### Dependencies

Features 03, 05, 06, and 09.

## Feature 12 — Integration Tests and Example Agent

### Goal

Prove the MVP works end-to-end from LangChain agent to Forge workspace execution.

### Owned Paths

```text
tests/integration/test_end_to_end.py
tests/integration/test_langchain_agent.py
examples/langchain_deep_agent.py
examples/basic_workspace.py
```

### HLD

Integration tests should exercise the user-visible product, not just individual units. They should be allowed to require Docker and should be skippable when Docker is unavailable.

### LLD

Tests:

- create workspace,
- write file,
- execute command,
- snapshot and restore,
- export artifact,
- use `ForgeSandbox` with Deep Agents,
- verify workspace reuse by thread ID,
- verify cleanup behavior.

### Acceptance Criteria

- End-to-end test passes on a machine with Docker.
- Tests skip clearly when Docker is unavailable.
- Example scripts are runnable and documented.

### Dependencies

All previous features.

## Merge Sequence

Recommended merge order:

1. Feature 01.
2. Feature 02.
3. Feature 03.
4. Feature 04.
5. Feature 05.
6. Feature 06.
7. Feature 07 and 08 in either order.
8. Feature 09.
9. Feature 10.
10. Feature 11.
11. Feature 12.

## Definition of Done for MVP

The MVP is done when:

- Python package installs locally.
- Local workspace store persists workspace files and metadata.
- Docker runtime executes commands with stdout, stderr, exit code, and timeout.
- File service supports LangChain-required operations.
- Snapshots and artifacts work.
- `ForgeSandbox` works with LangChain Deep Agents.
- CLI supports common debugging flows.
- TTL cleanup prevents unbounded local workspace growth.
- End-to-end tests pass with Docker.
