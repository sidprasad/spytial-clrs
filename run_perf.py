#!/usr/bin/env python3
"""
Run perf benchmarks for spytial-clrs data structures.

Copies notebooks to a temp directory, injects RUN_PERF = True via text
replacement on the raw .ipynb JSON, executes them with jupyter nbconvert,
and collects the output JSON files into /app/results/.

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
    print(f"  Executing {os.path.basename(notebook_path)} ...")
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
        print(f"  FAILED (exit code {result.returncode})")
        if result.stderr:
            print(result.stderr[-2000:])  # last 2000 chars of stderr
        return False
    print(f"  OK")
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
                print(f"  Warning: could not read {fpath}: {e}")
    return collected


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

    os.makedirs(RESULTS_DIR, exist_ok=True)

    all_results = {}
    failed = []

    # Work in a temp directory so originals are never touched
    with tempfile.TemporaryDirectory(prefix="spytial_perf_") as tmpdir:
        # Copy entire src/ so relative imports (perf_utils) and img/ refs work
        work_dir = os.path.join(tmpdir, "src")
        shutil.copytree(NOTEBOOK_DIR, work_dir)

        for notebook_name in notebooks:
            print(f"\n{'='*60}")
            print(f"  {notebook_name}")
            print(f"{'='*60}")

            nb_path = os.path.join(work_dir, notebook_name)
            if not os.path.exists(nb_path):
                print(f"  ERROR: {nb_path} not found")
                failed.append(notebook_name)
                continue

            inject_run_perf(nb_path)
            success = execute_notebook(nb_path, cwd=work_dir)

            if success:
                results = collect_results(work_dir, notebook_name)
                all_results.update(results)
                # Copy individual result files to RESULTS_DIR
                for fname, data in results.items():
                    out_path = os.path.join(RESULTS_DIR, fname)
                    with open(out_path, "w") as f:
                        json.dump(data, f, indent=2)
                print(f"  Collected {len(results)} result file(s)")
            else:
                failed.append(notebook_name)

    # Write summary
    summary = {
        "notebooks_run": [nb for nb in notebooks if nb not in failed],
        "notebooks_failed": failed,
        "result_files": sorted(all_results.keys()),
        "total_results": len(all_results),
    }
    summary_path = os.path.join(RESULTS_DIR, "perf_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Succeeded: {len(summary['notebooks_run'])}")
    print(f"  Failed:    {len(failed)}")
    print(f"  Results:   {len(all_results)} files -> {RESULTS_DIR}/")
    print(f"  Summary:   {summary_path}")

    if failed:
        print(f"\n  Failed notebooks: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
