#!/bin/bash
set -e

show_help() {
    cat <<'EOF'
Usage: docker run [OPTIONS] spytial-clrs [COMMAND]

SpyTial CLRS — Interactive data structure notebooks & perf benchmarks.

Commands:
  (default)                  Start JupyterLab on port 8888
  --perf <target> [target…]  Run performance benchmarks and output JSON results
  --diagnose                 Check environment (versions, timings, binaries)
  --help                     Show this help message

Perf targets:
  all                        Run benchmarks for every data structure
  <structure>                Run by structure name (e.g. hash_table_chaining, bstree)
  <notebook>                 Run by notebook stem (e.g. trees, heaps, graphs)

  Structures: direct_address, hash_table_chaining, singly_linked_list,
    doubly_linked_list, circular_doubly_linked_list, unweighted_graph_adjmatrix,
    weighted_graph, mst_graph, scc_graph, topo_sort_dag, memoization_matrix,
    disjoint_set, max_heap, fibonacci_heap, array_stack, array_queue,
    huffmantree, bstree, rbtree, ostree, btree, vebtree, intervaltree

Examples:
  docker run -p 8888:8888 spytial-clrs
      Serve notebooks at http://localhost:8888

  docker run spytial-clrs --perf all
      Run all benchmarks; mean renderLayout times printed to stdout

  docker run spytial-clrs --perf trees heaps
      Run benchmarks for trees.ipynb and heaps.ipynb only

  docker run -v $(pwd)/results:/app/results spytial-clrs --perf all
      Same as above, but also write full JSON results to ./results/
EOF
}

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
fi

if [ "$1" = "--diagnose" ]; then
    python - <<'PYEOF'
import sys, os, time, shutil, subprocess

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"

def check(label, ok, detail=""):
    icon = PASS if ok else FAIL
    line = f"  {icon} {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return ok

print("\n=== SpyTial CLRS — Environment Diagnostics ===\n")

# ── Python ────────────────────────────────────────────────────────────────────
print("Python")
check("version", True, sys.version.split()[0])

# ── Key packages ─────────────────────────────────────────────────────────────
print("\nPackages")
for pkg, imp in [
    ("spytial-diagramming", "spytial"),
    ("jupyterlab",          "jupyterlab"),
    ("nbconvert",           "nbconvert"),
    ("ipykernel",           "ipykernel"),
    ("selenium",            "selenium"),
]:
    try:
        mod = __import__(imp)
        ver = getattr(mod, "__version__", "unknown")
        check(pkg, True, ver)
    except ImportError as e:
        check(pkg, False, str(e))

# ── Binaries ─────────────────────────────────────────────────────────────────
print("\nBinaries")
for label, path in [
    ("chromium",     os.environ.get("CHROMIUM_BIN",    "/usr/bin/chromium")),
    ("chromedriver", os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")),
    ("jupyter",      shutil.which("jupyter") or "(not found)"),
]:
    exists = os.path.isfile(path)
    check(label, exists, path)

# ── Selenium import time (key for kernel startup) ─────────────────────────────
print("\nStartup timings")
t0 = time.perf_counter()
try:
    from selenium.webdriver.chrome import webdriver as _cw
    selenium_ms = (time.perf_counter() - t0) * 1000
    ok = selenium_ms < 10_000
    icon = PASS if ok else WARN
    print(f"  {icon} selenium import  ({selenium_ms:.0f} ms{'  ← slow; may cause kernel_info timeout' if not ok else ''})")
except Exception as e:
    print(f"  {FAIL} selenium import failed: {e}")

# ── Kernel startup smoke-test ─────────────────────────────────────────────────
print("\nKernel smoke-test")
t0 = time.perf_counter()
try:
    result = subprocess.run(
        ["jupyter", "kernelspec", "list"],
        capture_output=True, text=True, timeout=30,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    ok = result.returncode == 0
    check("kernelspec list", ok, f"{elapsed:.0f} ms")
    if ok:
        for line in result.stdout.strip().splitlines()[1:]:
            print(f"       {line.strip()}")
except subprocess.TimeoutExpired:
    print(f"  {FAIL} kernelspec list timed out after 30 s")
except Exception as e:
    print(f"  {FAIL} kernelspec list: {e}")

# ── Memory ────────────────────────────────────────────────────────────────────
print("\nResources")
try:
    with open("/proc/meminfo") as f:
        lines = {k: v for k, v in (l.split(":", 1) for l in f if ":" in l)}
    total_kb  = int(lines["MemTotal"].split()[0])
    avail_kb  = int(lines["MemAvailable"].split()[0])
    total_mb  = total_kb  // 1024
    avail_mb  = avail_kb  // 1024
    ok = avail_mb >= 512
    check("memory available", ok, f"{avail_mb} MB free of {total_mb} MB total")
    if not ok:
        print(f"       ↑ low memory may cause slow kernel startup or OOM during perf runs")
except Exception:
    print(f"  {WARN} could not read /proc/meminfo")

try:
    cpu_count = os.cpu_count() or 1
    check("CPU cores", True, str(cpu_count))
except Exception:
    pass

print()
PYEOF
    exit $?
fi

if [ "$1" = "--perf" ]; then
    shift
    exec python /app/run_perf.py "$@"
fi

# Default: serve notebooks via JupyterLab
exec jupyter lab \
    --ip=0.0.0.0 \
    --port=8888 \
    --no-browser \
    --allow-root \
    --notebook-dir=/app/src \
    --ServerApp.token='' \
    --ServerApp.password=''
