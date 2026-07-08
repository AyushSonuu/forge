"""forged — Forge daemon entrypoint. Full implementation lands in branch 07/11."""
from __future__ import annotations

import sys


def main() -> int:
    """Placeholder daemon entrypoint until branch 07 wires FastAPI + uvicorn."""
    print(
        "forged: server not yet available — implemented in branch 07 (feat/07-http). "
        "See docs/mvp-implementation-plan.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
