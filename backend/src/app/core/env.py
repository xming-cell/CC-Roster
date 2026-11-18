"""Subprocess environment merging.

Windows environment names are case-insensitive, but Python dicts and some runtimes
(for example Bun) look up exact keys. Parent environments usually provide
``SYSTEMROOT``; also fill ``SystemRoot`` so children do not report it missing.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


def merge_process_env(overrides: Mapping[str, str]) -> dict[str, str]:
    """Merge tool overrides into the parent environment without mutating inputs."""
    merged = {**os.environ, **overrides}
    system_root = merged.get("SystemRoot") or merged.get("SYSTEMROOT")
    if system_root:
        merged["SystemRoot"] = system_root
        merged["SYSTEMROOT"] = system_root
    return merged
