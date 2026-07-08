"""Forge — resource-pooled workspace runtime for AI agents.

Public API is intentionally small at import time; heavier subsystems (server,
drivers, langchain adapter) are only imported when used.
"""
from __future__ import annotations

__version__ = "0.1.0.dev0"

__all__ = ["__version__"]
