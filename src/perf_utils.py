"""
Centralized performance testing utilities for spytial-clrs notebooks.

Provides:
  - Common perf config (SIZES, PI)
  - get_perf_path(): file path for size-based perf results

The benchmark code itself lives in perf_recipes.py and is injected into notebook
copies at runtime by run_perf.py — it is no longer part of the notebooks.
"""

# ── Configuration ───────────────────────────────────────────────────────────────
PERF_BASE = "spytial_perf"
PI = 20
SIZES = [5, 10, 25, 50]         # sizes for the "fixed-size" perf runs


def get_perf_path(structure: str, size: int) -> str:
    """Return the JSON output path for a fixed-size perf run."""
    return f"{PERF_BASE}_{structure}_{size}.json"
