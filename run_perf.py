#!/usr/bin/env python3
"""
Run perf benchmarks for spytial-clrs data structures.

Copies notebooks to a temp directory, injects RUN_PERF = True via text
replacement on the raw .ipynb JSON, executes them with jupyter nbconvert,
and collects the output JSON files.

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


def inject_run_perf(notebook_path):
    """Set RUN_PERF = True in the notebook by editing the parsed JSON source lines."""
    with open(notebook_path, "r") as f:
        nb = json.load(f)

    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        new_source = []
        for line in cell.get("source", []):
            stripped = line.rstrip("\n")
            if stripped.strip() == "RUN_PERF = False":
                new_source.append("RUN_PERF = True\n")
            else:
                new_source.append(line)
        cell["source"] = new_source

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
    print(f"\n{'='*60}")
    print(f"  RESULTS: Mean renderLayout time (ms)")
    print(f"{'='*60}")
    size_headers = "".join(f"{'n=' + str(s):>10}" for s in sizes)
    print(f"  {'Structure':<30}{size_headers}")
    print(f"  {'-'*30}{'-'*10*len(sizes)}")

    for struct in sorted(by_structure.keys()):
        row = f"  {struct:<30}"
        for s in sizes:
            data = by_structure[struct].get(s)
            if data and "renderLayout" in data:
                avg = data["renderLayout"]["avg"]
                row += f"{avg:>10.2f}"
            else:
                row += f"{'—':>10}"
        print(row)

    print()


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

            inject_run_perf(nb_path)
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
