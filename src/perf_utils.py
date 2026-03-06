"""
Centralized performance testing utilities for spytial-clrs notebooks.

Provides:
  - Common perf config (SIZES, PI, RUN_PERF, etc.)
  - get_perf_path(): file path for size-based perf results
  - find_threshold_sizes(): keep increasing N until rendering crosses time thresholds
"""

import time
import json
import os
import tempfile

# ── Configuration ──────────────────────────────────────────────────────────────
PERF_BASE = "spytial_perf"
PI = 20
SIZES = [5, 10, 25, 50]         # sizes for the "fixed-size" perf runs
THRESHOLDS = [0.1, 1.0, 10.0]   # seconds
THRESHOLD_AVG_RUNS = 20           # averaging runs per size in threshold mode


def get_perf_path(structure: str, size: int) -> str:
    """Return the JSON output path for a fixed-size perf run."""
    return f"{PERF_BASE}_{structure}_{size}.json"


# ── Threshold-based performance testing ────────────────────────────────────────

def _time_render(diagram_fn, build_fn, size, avg_runs, timeout):
    """
    Build the structure, render via diagram() with perf_iterations,
    read back the browser-measured timings from the perf JSON, clean up.

    ``timeout`` is in seconds — passed directly to diagram()'s built-in
    timeout parameter which handles Chrome lifecycle gracefully.

    Returns a dict with avg/median/p95/min/max in **seconds**, or None
    if the perf JSON could not be read (e.g. the browser timed out before
    completing any iteration).
    """
    obj = build_fn(size)

    # Use a temp file for the perf output — diagram() writes browser timings here
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="spytial_perf_tmp_")
    os.close(fd)

    try:
        print(f"Trying Size {size}")
        print(f"  Running {avg_runs} iterations (timeout: {timeout}s)...")
        diagram_fn(
            obj,
            method="browser",
            headless=True,
            perf_path=tmp_path,
            perf_iterations=avg_runs,
            timeout=timeout,
        )
    except Exception as e:
        print(f"  Error at size {size}: {e}")
        return None

    try:
        # If the browser timed out it may write an empty / partial file
        if os.path.getsize(tmp_path) == 0:
            return None

        with open(tmp_path) as f:
            perf_data = json.load(f)

        completed = perf_data.get("completed", False)
        actual_iters = perf_data.get("iterations", 0)

        if actual_iters == 0:
            # No iterations completed at all — no usable data
            return None

        # totalTime values are in milliseconds
        total = perf_data["totalTime"]
        result = {
            "avg":    total["avg"]    / 1000.0,
            "median": total["median"] / 1000.0,
            "p95":    total["p95"]    / 1000.0,
            "min":    total["min"]    / 1000.0,
            "max":    total["max"]    / 1000.0,
            "iterations": actual_iters,
            "partial": not completed,
        }
        if not completed:
            print(f"  ⚠ Partial result at size {size}: {actual_iters}/{avg_runs} iterations")
        return result
    except (json.JSONDecodeError, KeyError, OSError):
        return None
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def find_threshold_sizes(
    structure_name: str,
    build_fn,
    *,
    start_size: int = 5,
    max_size: int = 10 * 1000,
    growth_factor: float = 1.5,
    avg_runs: int = THRESHOLD_AVG_RUNS,
    thresholds: list = THRESHOLDS,
    timeout: int = 300,
):
    """
    Two-phase threshold finder.

    **Phase 1 – Scan:** exponentially increase size, measure each, and
    record every data point.  Don't stop for intermediate threshold
    crossings — keep going until we timeout, hit max_size, or cross the
    *largest* threshold.  This minimises Chrome launches.

    **Phase 2 – Refine:** for each threshold, find the tightest bracket
    ``[lo, hi]`` from the scan data where ``lo`` is below the threshold
    and ``hi`` is at-or-above (or timed-out).  Binary-search inside
    that bracket only if the gap is large enough to matter.

    Parameters
    ----------
    structure_name : str
        Label used in output / file names.
    build_fn : callable(int) -> object
        Given a size, builds and returns the diagrammable object.
    start_size : int
        First size to try.
    max_size : int
        Stop even if thresholds haven't all been crossed.
    growth_factor : float
        Multiplicative increase for the next size (at least +1).
    avg_runs : int
        Rendering iterations per size (passed as ``perf_iterations``).
    thresholds : list[float]
        Time thresholds in seconds (default: 0.1, 1.0, 10.0).
    timeout : int
        Base timeout in seconds for the headless browser render.

    Returns
    -------
    results : dict[float, dict | None]
        Mapping threshold → {size, avg_time} or None if not reached.
    """
    from spytial import diagram as diagram_fn

    if thresholds is None:
        thresholds = list(THRESHOLDS)

    thresholds = sorted(thresholds)
    max_threshold = thresholds[-1]

    all_data = []                           # in-memory timing log
    timing_cache = {}                       # size → timing dict
    timeout_at = None                       # size that timed out (upper fence)

    TIMEOUT_CAP = 220  # seconds — absolute max for any single Chrome session

    # ── Load cached data from a previous run if the file exists ───────────────
    cache_path = f"{PERF_BASE}_{structure_name}_thresholds.json"
    prev_results = {}                       # threshold → result dict (already resolved)
    try:
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                prev = json.load(f)
            for entry in prev.get("all_data", []):
                sz = entry["size"]
                stats = {k: entry[k] for k in ("avg", "median", "p95", "min", "max", "iterations") if k in entry}
                if "avg" in stats:
                    timing_cache[sz] = stats
                    all_data.append({"size": sz, **stats})
            # Re-derive thresholds from cached all_data
            # (Phase 2 refinement data may exist in all_data but not be
            #  reflected in the saved "thresholds" section — e.g. if the
            #  run was interrupted before the final save.)
            for t in thresholds:
                for sz, st in sorted(timing_cache.items()):
                    if st.get("avg", 0) >= t * 0.95:
                        prev_results[t] = {"size": sz, **st}
                        break   # sorted by size → first crossing is tightest
            if timing_cache:
                print(f"Loaded {len(timing_cache)} cached data points from {cache_path}")
            if prev_results:
                print(f"Previously resolved thresholds: {', '.join(f'{t}s' for t in sorted(prev_results))}")
    except (json.JSONDecodeError, KeyError, OSError) as e:
        print(f"Could not load cache ({e}), starting fresh")

    # Figure out which thresholds still need work
    remaining_thresholds = [t for t in thresholds if t not in prev_results]
    if not remaining_thresholds:
        print(f"\nAll thresholds already resolved from previous run!")
        # Still print summary and return
        results = {t: prev_results.get(t) for t in thresholds}
        print(f"\n--- Summary: {structure_name} ---")
        for t in thresholds:
            r = results.get(t)
            if r:
                print(f"  {t:>5.1f}s threshold: crossed at size {r['size']} "
                      f"(avg {r['avg']:.4f}s, median {r['median']:.4f}s, p95 {r['p95']:.4f}s) [cached]")
            else:
                print(f"  {t:>5.1f}s threshold: NOT reached (max size tested: {max_size})")
        return results, all_data

    max_threshold = remaining_thresholds[-1]  # largest remaining
    print(f"Remaining thresholds to find: {', '.join(f'{t}s' for t in remaining_thresholds)}")

    # results tracks resolved thresholds (seeded from prev_results, updated live)
    results = dict(prev_results)
    cache_path_out = f"{PERF_BASE}_{structure_name}_thresholds.json"

    def _save_progress():
        """Write current state to disk so nothing is lost on crash."""
        seen = {}
        for entry in all_data:
            seen[entry["size"]] = entry
        deduped = sorted(seen.values(), key=lambda d: d["size"])
        output = {
            "structure": structure_name,
            "config": {
                "start_size": start_size,
                "max_size": max_size,
                "growth_factor": growth_factor,
                "avg_runs": avg_runs,
            },
            "thresholds": {
                str(t): results.get(t) for t in thresholds
            },
            "all_data": deduped,
        }
        with open(cache_path_out, "w") as f:
            json.dump(output, f, indent=2)

    def _timeout_for(avg_s: float | None) -> int:
        """Timeout (seconds) = avg_per_iter × avg_runs × 3, clamped to TIMEOUT_CAP."""
        if avg_s is None:
            return min(timeout, TIMEOUT_CAP)
        expected_total = avg_s * avg_runs
        return min(max(timeout, int(expected_total * 3)), TIMEOUT_CAP)

    last_observed_s = None

    def _measure(sz):
        """Measure (with cache).  Returns timing dict or None on failure."""
        nonlocal last_observed_s
        if sz in timing_cache:
            # Update last_observed_s so adaptive timeout stays calibrated
            last_observed_s = timing_cache[sz]["avg"]
            return timing_cache[sz]
        cur_timeout = _timeout_for(last_observed_s)
        try:
            stats = _time_render(diagram_fn, build_fn, sz, avg_runs, cur_timeout)
        except Exception as e:
            print(f"  Error at size {sz}: {e}")
            return None
        if stats is None:
            print(f"  Timeout / incomplete at size {sz} (timeout was {cur_timeout}s)")
            return None
        timing_cache[sz] = stats
        all_data.append({"size": sz, **stats})
        last_observed_s = stats["avg"]
        # Check if any thresholds are now crossed and update results
        # (update even if already set, when this size is smaller — tighter bound)
        for t in thresholds:
            if stats["avg"] >= t * 0.95 and (t not in results or sz < results[t]["size"]):
                results[t] = {"size": sz, **stats}
        _save_progress()
        return stats

    # ── Phase 1: Scan ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"Threshold Performance: {structure_name}")
    print(f"{'=' * 60}")

    # Check if cached data already brackets remaining thresholds
    skip_scan = False
    if timing_cache:
        cached_crossing = [sz for sz, st in timing_cache.items() if st["avg"] >= max_threshold]
        if cached_crossing:
            skip_scan = True
            print(f"\nPhase 1 — skipped (cached data already crosses {max_threshold}s)")
            # Print cached summary table
            print(f"{'Size':>8} | {'Avg (s)':>10} | {'Median (s)':>10} | {'P95 (s)':>10} | {'Source':>8}")
            print(f"{'-' * 8}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 8}")
            for sz, st in sorted(timing_cache.items()):
                print(f"{sz:>8} | {st['avg']:>10.4f} | {st['median']:>10.4f} | {st['p95']:>10.4f} | {'cached':>8}")

    if not skip_scan:
        # Smart start: jump ahead to the highest cached size still below
        # max_threshold so we don't re-scan confirmed-fast sizes
        scan_start = start_size
        if timing_cache:
            below = [sz for sz, st in timing_cache.items() if st["avg"] < max_threshold]
            if below:
                highest_below = max(below)
                last_observed_s = timing_cache[highest_below]["avg"]

                # Use the same adaptive logic as the scan loop:
                # if the highest cached avg is within 10% of the next
                # uncrossed threshold, creep at 1.1× instead of growth_factor
                next_uncrossed = None
                for t in thresholds:
                    if t not in results and last_observed_s < t:
                        next_uncrossed = t
                        break
                if next_uncrossed is not None and last_observed_s >= next_uncrossed * 0.9:
                    scan_start = max(highest_below + 1, int(highest_below * 1.1))
                else:
                    scan_start = max(highest_below + 1, int(highest_below * growth_factor))

        print(f"\nPhase 1 — exponential scan (starting at size {scan_start})")
        print(f"{'Size':>8} | {'Avg (s)':>10} | {'Median (s)':>10} | {'P95 (s)':>10} | {'Source':>8}")
        print(f"{'-' * 8}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 8}")

        # Print cached points for context (they won't be re-measured)
        if timing_cache:
            for sz, st in sorted(timing_cache.items()):
                if sz < scan_start:
                    print(f"{sz:>8} | {st['avg']:>10.4f} | {st['median']:>10.4f} | {st['p95']:>10.4f} | {'cached':>8}")

        size = scan_start
        while size <= max_size:
            size = int(size)
            was_cached = size in timing_cache
            stats = _measure(size)

            if stats is None:
                timeout_at = size
                print(f"{'⚠ ' + str(size):>8} | {'TIMEOUT':>10} |            |            |")
                break

            avg = stats["avg"]
            tag = "cached" if was_cached else "fresh"
            print(f"{size:>8} | {avg:>10.4f} | {stats['median']:>10.4f} | {stats['p95']:>10.4f} | {tag:>8}")

            if avg >= max_threshold:
                # Crossed the biggest threshold — no need to keep scanning
                break

            # Adaptive growth: if we're within 10% of the next uncrossed
            # threshold, slow down to 10% increments so we land on it
            # without overshooting into timeout territory.
            next_uncrossed = None
            for t in thresholds:
                if t not in results and avg < t:
                    next_uncrossed = t
                    break
            if next_uncrossed is not None and avg >= next_uncrossed * 0.9:
                # Close to threshold — creep forward
                size = max(size + 1, int(size * 1.1))
            else:
                size = max(size + 1, int(size * growth_factor))

    # ── Phase 2: Refine ──────────────────────────────────────────────────────
    # Build sorted list of successful measurements
    measured = sorted(timing_cache.items())  # [(size, stats), ...]

    # results already seeded from prev_results and updated during scan
    needs_search = []

    for t in remaining_thresholds:
        # Find bracket: largest size below t (lo), smallest size >= t (hi)
        lo_size, lo_stats = None, None
        hi_size, hi_stats = None, None

        for sz, st in measured:
            if st["avg"] < t * 0.95:
                lo_size, lo_stats = sz, st
            else:
                if hi_size is None:
                    hi_size, hi_stats = sz, st

        if hi_size is not None:
            # Threshold was crossed by a measured data point
            if lo_size is not None and hi_size - lo_size > 2:
                # Gap big enough to binary search
                needs_search.append((t, lo_size, hi_size, hi_stats))
            else:
                # Already tight — use hi directly
                results[t] = {"size": hi_size, **hi_stats}
        elif timeout_at is not None:
            # Never crossed by a successful measurement, but we had a timeout.
            # The threshold is somewhere between the last successful size and
            # the timed-out size.
            if lo_size is not None and timeout_at - lo_size > 2:
                needs_search.append((t, lo_size, timeout_at, None))
            elif lo_size is not None:
                # Gap too small — the timed-out size is the answer (approx)
                results[t] = None  # can't pin it down
            else:
                results[t] = None
        else:
            results[t] = None  # never reached

    if needs_search:
        print(f"\nPhase 2 — binary search refinement")
        for t, lo, hi, hi_stats in needs_search:
            best_size, best_stats = (hi, hi_stats) if hi_stats is not None else (None, None)
            print(f"  {t}s threshold: searching [{lo+1}..{hi-1}]", end="", flush=True)

            while lo + 1 < hi:
                mid = (lo + hi) // 2
                mid_stats = _measure(mid)
                if mid_stats is None:
                    # timed out → too slow → search lower
                    hi = mid
                elif mid_stats["avg"] >= t * 0.95:
                    best_size, best_stats = mid, mid_stats
                    hi = mid
                else:
                    lo = mid

            if best_stats is not None:
                print(f" → size {best_size} ({best_stats['avg']:.4f}s)")
                results[t] = {"size": best_size, **best_stats}
            else:
                print(f" → could not pin down")
                results[t] = None
    else:
        print(f"\nPhase 2 — no refinement needed")

    # Fill in any thresholds that were tight enough (set above)
    # (results dict already has them)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n--- Summary: {structure_name} ---")
    for t in thresholds:
        r = results.get(t)
        tag = " [cached]" if t in prev_results and r == prev_results[t] else ""
        if r:
            print(f"  {t:>5.1f}s threshold: crossed at size {r['size']} "
                  f"(avg {r['avg']:.4f}s, median {r['median']:.4f}s, p95 {r['p95']:.4f}s){tag}")
        else:
            print(f"  {t:>5.1f}s threshold: NOT reached (max size tested: {max_size})")

    # ── Final save ─────────────────────────────────────────────────────────────
    _save_progress()
    print(f"  Results saved to {cache_path_out}")

    return results, all_data
