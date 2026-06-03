#!/usr/bin/env python3
"""
Run perf benchmarks for spytial-clrs data structures.

Copies notebooks to a temp directory, appends a generated benchmark cell per
structure (built from perf_recipes.RECIPES) to the raw .ipynb JSON, executes
them with jupyter nbconvert, and collects the output JSON files.

The benchmark code no longer lives in the notebooks — the notebooks only define
the structures. Each appended cell builds a structure at the configured sizes and
calls diagram(..., perf_path=...) so the browser writes timing JSON.

Results are printed to stdout as a summary table showing mean renderLayout
times per structure and size. JSON files are still written to RESULTS_DIR
if the directory is mounted.

Usage:
    python run_perf.py all                     # every notebook with perf blocks
    python run_perf.py hash_table_chaining     # by structure name
    python run_perf.py hash-tables             # by notebook stem
    python run_perf.py trees heaps             # multiple targets
"""

import sys
import os
import json
import shutil
import subprocess
import tempfile
import glob
import itertools
import threading
import time
import re

from perf_recipes import RECIPES

NOTEBOOK_DIR = os.environ.get("NOTEBOOK_DIR", "/app/src")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/app/results")

# structure_name -> notebook filename (without path)
STRUCTURE_TO_NOTEBOOK = {
    "direct_address":               "hash-tables.ipynb",
    "hash_table_chaining":          "hash-tables.ipynb",
    "singly_linked_list":           "linked-lists.ipynb",
    "doubly_linked_list":           "linked-lists.ipynb",
    "circular_doubly_linked_list":  "linked-lists.ipynb",
    "unweighted_graph_adjmatrix":   "graphs.ipynb",
    "weighted_graph":               "graphs.ipynb",
    "mst_graph":                    "graphs.ipynb",
    "scc_graph":                    "graphs.ipynb",
    "topo_sort_dag":                "graphs.ipynb",
    "memoization_matrix":           "memoization.ipynb",
    "disjoint_set":                 "disjoint-sets.ipynb",
    "max_heap":                     "heaps.ipynb",
    "fibonacci_heap":               "heaps.ipynb",
    "array_stack":                  "stacksqueues.ipynb",
    "array_queue":                  "stacksqueues.ipynb",
    "huffmantree":                  "huffman.ipynb",
    "bstree":                       "trees.ipynb",
    "rbtree":                       "trees.ipynb",
    "ostree":                       "trees.ipynb",
    "btree":                        "trees.ipynb",
    "vebtree":                      "trees.ipynb",
    "intervaltree":                 "trees.ipynb",
}

# Notebooks that contain RUN_PERF blocks (simple-bdd.ipynb has none)
PERF_NOTEBOOKS = sorted(set(STRUCTURE_TO_NOTEBOOK.values()))

# Reverse lookup: notebook -> list of structures it contains
NOTEBOOK_STRUCTURES = {}
for struct, nb in STRUCTURE_TO_NOTEBOOK.items():
    NOTEBOOK_STRUCTURES.setdefault(nb, []).append(struct)


class Spinner:
    """Animated spinner that shows what's currently being timed."""
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message=""):
        self._message = message
        self._stop = threading.Event()
        self._thread = None

    def start(self, message=None):
        if message is not None:
            self._message = message
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, message):
        self._message = message

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
            self._thread = None
        # Clear the spinner line
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def _spin(self):
        for frame in itertools.cycle(self.FRAMES):
            if self._stop.is_set():
                break
            sys.stderr.write(f"\r\033[K{frame} {self._message}")
            sys.stderr.flush()
            time.sleep(0.1)


def resolve_targets(args):
    """Resolve CLI args into a deduplicated list of notebook filenames."""
    notebooks = []
    for arg in args:
        if arg == "all":
            return list(PERF_NOTEBOOKS)
        # Try as structure name
        if arg in STRUCTURE_TO_NOTEBOOK:
            notebooks.append(STRUCTURE_TO_NOTEBOOK[arg])
            continue
        # Try as notebook stem (with or without .ipynb)
        stem = arg if arg.endswith(".ipynb") else f"{arg}.ipynb"
        if stem in PERF_NOTEBOOKS:
            notebooks.append(stem)
            continue
        print(f"ERROR: Unknown target '{arg}'")
        print(f"  Valid structure names: {', '.join(sorted(STRUCTURE_TO_NOTEBOOK))}")
        print(f"  Valid notebook stems:  {', '.join(nb.removesuffix('.ipynb') for nb in PERF_NOTEBOOKS)}")
        print(f"  Or use 'all' to run everything.")
        sys.exit(1)
    # deduplicate while preserving order
    seen = set()
    return [nb for nb in notebooks if not (nb in seen or seen.add(nb))]


def _render_perf_cell(struct):
    """Build the source for one structure's benchmark cell from its recipe.

    The cell defines build(size) and renders the structure at each size via
    diagram(..., perf_path=...). It is appended at the end of the notebook, so
    the structure classes and spytial helpers from earlier cells are in scope.
    """
    recipe = RECIPES[struct]
    build_src = recipe["build"].strip("\n")
    label = recipe.get("label", "size")
    timeout = recipe.get("timeout")
    sizes = recipe.get("sizes")
    sizes_expr = repr(sizes) if sizes is not None else "SIZES"

    diagram_kwargs = [
        'method="browser"',
        f'perf_path=get_perf_path("{struct}", {label})',
        "perf_iterations=PI",
        "headless=True",
    ]
    if timeout is not None:
        diagram_kwargs.append(f"timeout={timeout}")
    kwargs = ", ".join(diagram_kwargs)

    return (
        f"# Auto-generated perf benchmark for {struct} (see perf_recipes.py)\n"
        "import random\n"
        "from perf_utils import get_perf_path, PI, SIZES\n"
        "\n"
        f"{build_src}\n"
        "\n"
        f"for size in {sizes_expr}:\n"
        f"    diagram(build(size), {kwargs})\n"
    )


def append_perf_cells(notebook_path, structures):
    """Append one generated benchmark cell per structure to the notebook JSON."""
    with open(notebook_path, "r") as f:
        nb = json.load(f)

    for struct in structures:
        if struct not in RECIPES:
            sys.stderr.write(f"  Warning: no perf recipe for '{struct}', skipping\n")
            continue
        nb["cells"].append({
            "cell_type": "code",
            "id": f"perf-{struct}",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": _render_perf_cell(struct).splitlines(keepends=True),
        })

    with open(notebook_path, "w") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")


def execute_notebook(notebook_path, cwd):
    """Execute a notebook in-place using jupyter nbconvert."""
    result = subprocess.run(
        [
            "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.timeout=-1",
            "--ExecutePreprocessor.kernel_info_timeout=300",
            notebook_path,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if result.stderr:
            sys.stderr.write(result.stderr[-2000:])
        return False
    return True


def collect_results(cwd, notebook_name):
    """Collect spytial_perf_*.json files produced by the notebook run."""
    structures = NOTEBOOK_STRUCTURES.get(notebook_name, [])
    collected = {}
    for struct in structures:
        pattern = os.path.join(cwd, f"spytial_perf_{struct}_*.json")
        files = sorted(glob.glob(pattern))
        for fpath in files:
            try:
                with open(fpath) as f:
                    data = json.load(f)
                key = os.path.basename(fpath)
                collected[key] = data
            except (json.JSONDecodeError, OSError) as e:
                sys.stderr.write(f"  Warning: could not read {fpath}: {e}\n")
    return collected


def extract_structure_and_size(filename):
    """Extract structure name and size from a perf result filename.

    e.g. 'spytial_perf_disjoint_set_5.json' -> ('disjoint_set', 5)
    """
    stem = filename.removesuffix(".json").removeprefix("spytial_perf_")
    # Match against known structure names to handle underscores in names
    for struct in sorted(STRUCTURE_TO_NOTEBOOK.keys(), key=len, reverse=True):
        if stem.startswith(struct + "_"):
            rest = stem[len(struct) + 1:]
            if rest.isdigit():
                return struct, int(rest)
    # Fallback: last segment is the size
    match = re.match(r"^(.+)_(\d+)$", stem)
    if match:
        return match.group(1), int(match.group(2))
    return stem, None


def print_results_table(all_results):
    """Print a summary table of mean renderLayout times to stdout."""
    # Group results by structure
    by_structure = {}
    all_sizes = set()
    for fname, data in all_results.items():
        struct, size = extract_structure_and_size(fname)
        if size is None:
            continue
        all_sizes.add(size)
        by_structure.setdefault(struct, {})[size] = data

    if not by_structure:
        return

    sizes = sorted(all_sizes)

    # Header
    col_w = 20  # width per size column
    print(f"\n{'='*70}")
    print(f"  RESULTS: Mean renderLayout time in ms (stddev)")
    print(f"{'='*70}")
    size_headers = "".join(f"{'n=' + str(s):>{col_w}}" for s in sizes)
    print(f"  {'Structure':<30}{size_headers}")
    print(f"  {'-'*30}{'-'*col_w*len(sizes)}")

    for struct in sorted(by_structure.keys()):
        row = f"  {struct:<30}"
        for s in sizes:
            data = by_structure[struct].get(s)
            if data and "renderLayout" in data:
                avg = data["renderLayout"]["avg"]
                sd = data["renderLayout"].get("stdDev", 0)
                cell = f"{avg:.2f} ({sd:.2f})"
                row += f"{cell:>{col_w}}"
            else:
                row += f"{'—':>{col_w}}"
        print(row)

    print()


def generate_charts(all_results):
    """Generate performance charts and save as PNG to RESULTS_DIR.

    Produces:
      - total_time_all_structures.png  (cross-structure comparison with Nielsen
        thresholds, log-scale y-axis)
      - Per-structure total_time_<name>.png charts
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import itertools as _itertools
        import seaborn as sns
    except ImportError as e:
        sys.stderr.write(f"  Warning: cannot generate charts ({e})\n")
        return

    # Build a tidy dataframe-like list of dicts from the raw results
    rows = []
    for fname, data in all_results.items():
        struct, size = extract_structure_and_size(fname)
        if size is None:
            continue
        for phase in ("generateLayout", "renderLayout", "totalTime"):
            if phase in data:
                rows.append({
                    "data_structure": struct,
                    "size": size,
                    "phase": phase,
                    "min": data[phase]["min"],
                    "max": data[phase]["max"],
                    "avg": data[phase]["avg"],
                    "median": data[phase]["median"],
                    "stdDev": data[phase].get("stdDev", 0),
                })

    if not rows:
        return

    # ── Cross-structure comparison (totalTime) ──────────────────────────────
    total_rows = [r for r in rows if r["phase"] == "totalTime"]
    if not total_rows:
        return

    ds_list = sorted({r["data_structure"] for r in total_rows})
    sizes = sorted({r["size"] for r in total_rows})
    n_ds = len(ds_list)

    base_pal = sns.color_palette("tab20", n_colors=min(20, max(1, n_ds)))
    if n_ds > 20:
        base_pal += sns.color_palette("hsv", n_colors=(n_ds - 20))
    palette = base_pal[:n_ds]

    markers = ["o", "s", "^", "D", "v", "<", ">", "p", "*", "h", "H", "X", "d", "P", "8"]
    marker_cycle = _itertools.cycle(markers)
    color_cycle = _itertools.cycle(palette)

    fig, ax = plt.subplots(figsize=(10, 6))

    for ds in ds_list:
        ds_rows = sorted(
            [r for r in total_rows if r["data_structure"] == ds],
            key=lambda r: r["size"],
        )
        if not ds_rows:
            continue
        xs = [r["size"] for r in ds_rows]
        ys = [r["avg"] / 1000.0 for r in ds_rows]  # ms -> seconds
        ax.plot(
            xs, ys,
            marker=next(marker_cycle),
            linestyle="-",
            linewidth=1.5,
            markersize=6,
            label=ds,
            color=next(color_cycle),
            alpha=0.9,
        )

    # Nielsen thresholds
    nielsen = [
        (0.1, "Instantaneous"),
        (1.0, "Continuous interaction"),
        (10.0, "Attention-sustaining"),
    ]
    for y, label in nielsen:
        ax.axhline(y=y, linestyle="--", linewidth=1.0, color="0.4", alpha=0.9)
        ax.text(
            sizes[-1] * 1.01, y, label,
            va="center", ha="left", fontsize=10, color="0.15",
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=2),
        )

    FONTSIZE = 12
    ax.set_xlabel("Size (nodes)", fontsize=FONTSIZE)
    ax.set_ylabel("Time (seconds)", fontsize=FONTSIZE)
    ax.set_title("Total Time Across All Data Structures", fontsize=FONTSIZE + 1)
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.25)
    ax.tick_params(axis="both", which="major", labelsize=FONTSIZE - 1)
    ax.legend(
        fontsize=9, ncol=4, loc="upper center",
        bbox_to_anchor=(0.5, -0.18), frameon=False,
    )
    plt.tight_layout(rect=(0, 0.12, 0.85, 1))

    out_path = os.path.join(RESULTS_DIR, "total_time_all_structures.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved to {out_path}")

    # ── Per-structure totalTime charts ──────────────────────────────────────
    colors = {
        "generateLayout": "#4ECDC4",
        "renderLayout": "#45B7D1",
        "totalTime": "#FFA07A",
    }
    focus_phases = ["generateLayout", "renderLayout", "totalTime"]

    for ds in ds_list:
        ds_total = sorted(
            [r for r in total_rows if r["data_structure"] == ds],
            key=lambda r: r["size"],
        )
        if not ds_total:
            continue

        fig_t, ax_t = plt.subplots(figsize=(8, 5))
        xs = [r["size"] for r in ds_total]
        ys = [r["avg"] for r in ds_total]
        errs = [r["stdDev"] for r in ds_total]
        mins = [r["min"] for r in ds_total]
        maxs = [r["max"] for r in ds_total]

        ax_t.errorbar(
            xs, ys, yerr=errs,
            marker="o", linewidth=2, capsize=5,
            label="mean +/- stdDev", color=colors["totalTime"],
        )
        ax_t.fill_between(xs, mins, maxs, alpha=0.2, color=colors["totalTime"], label="min-max range")
        ax_t.set_xlabel("Size (nodes)", fontsize=FONTSIZE)
        ax_t.set_ylabel("Time (ms)", fontsize=FONTSIZE)
        ax_t.set_title(f"{ds.upper()} - Total Time", fontsize=FONTSIZE, fontweight="bold")
        ax_t.grid(True, alpha=0.3)
        ax_t.legend(fontsize=FONTSIZE)
        plt.tight_layout()

        fname = os.path.join(RESULTS_DIR, f"total_time_{ds}.png")
        plt.savefig(fname, dpi=300, bbox_inches="tight")
        plt.close(fig_t)

    print(f"  Per-structure charts saved to {RESULTS_DIR}/")


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_perf.py <target> [target ...]")
        print("  target: 'all', a structure name, or a notebook stem")
        print(f"\n  Structures: {', '.join(sorted(STRUCTURE_TO_NOTEBOOK))}")
        print(f"  Notebooks:  {', '.join(nb.removesuffix('.ipynb') for nb in PERF_NOTEBOOKS)}")
        sys.exit(1)

    notebooks = resolve_targets(sys.argv[1:])
    print(f"Will run perf for: {', '.join(nb.removesuffix('.ipynb') for nb in notebooks)}")
    for nb in notebooks:
        print(f"  {nb}: {', '.join(NOTEBOOK_STRUCTURES[nb])}")

    all_results = {}
    failed = []
    spinner = Spinner()

    # Work in a temp directory so originals are never touched
    with tempfile.TemporaryDirectory(prefix="spytial_perf_") as tmpdir:
        # Copy entire src/ so relative imports (perf_utils) and img/ refs work
        work_dir = os.path.join(tmpdir, "src")
        shutil.copytree(NOTEBOOK_DIR, work_dir)

        for i, notebook_name in enumerate(notebooks, 1):
            structures = NOTEBOOK_STRUCTURES.get(notebook_name, [])
            label = ", ".join(structures)
            spinner.start(
                f"[{i}/{len(notebooks)}] Benchmarking {notebook_name} ({label})"
            )

            nb_path = os.path.join(work_dir, notebook_name)
            if not os.path.exists(nb_path):
                spinner.stop()
                print(f"  ERROR: {nb_path} not found")
                failed.append(notebook_name)
                continue

            append_perf_cells(nb_path, structures)
            success = execute_notebook(nb_path, cwd=work_dir)
            spinner.stop()

            if success:
                print(f"  [{i}/{len(notebooks)}] {notebook_name} ... OK")
                results = collect_results(work_dir, notebook_name)
                all_results.update(results)

                # Write JSON files to RESULTS_DIR if it exists or is mounted
                if os.path.isdir(RESULTS_DIR):
                    for fname, data in results.items():
                        out_path = os.path.join(RESULTS_DIR, fname)
                        with open(out_path, "w") as f:
                            json.dump(data, f, indent=2)
            else:
                print(f"  [{i}/{len(notebooks)}] {notebook_name} ... FAILED")
                failed.append(notebook_name)

    # Print the results table to stdout
    print_results_table(all_results)

    # Generate charts when running all structures
    if "all" in sys.argv[1:] and all_results and os.path.isdir(RESULTS_DIR):
        print("  Generating performance charts...")
        generate_charts(all_results)

    # Write summary JSON if RESULTS_DIR exists
    if os.path.isdir(RESULTS_DIR):
        summary = {
            "notebooks_run": [nb for nb in notebooks if nb not in failed],
            "notebooks_failed": failed,
            "result_files": sorted(all_results.keys()),
            "total_results": len(all_results),
        }
        summary_path = os.path.join(RESULTS_DIR, "perf_summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"  Full results written to {RESULTS_DIR}/")

    # Final status
    print(f"  Succeeded: {len(notebooks) - len(failed)}/{len(notebooks)} notebooks")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
