"""Ponte servidor ↔ núcleo: um processo filho por projeto, NDJSON por stdio."""

from __future__ import annotations

from . import allowlist, pool, protocolo, worker

__all__ = ["allowlist", "pool", "protocolo", "worker"]
