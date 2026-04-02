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
import sys, os, time, platform, subprocess, struct

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"

def status(label, ok, detail=""):
    icon = PASS if ok else (WARN if ok is None else FAIL)
    line = f"  {icon} {label}"
    if detail:
        line += f"  ({detail})"
    print(line)

print("\n=== SpyTial CLRS — Environment Diagnostics ===\n")

# ── Architecture / emulation ─────────────────────────────────────────────────
print("Platform")
machine = platform.machine()           # e.g. x86_64, aarch64
image_arch = "arm64" if "aarch" in machine else "amd64"
status("image arch", True, f"{machine} → {image_arch}")

# Detect QEMU emulation: /proc/cpuinfo on emulated aarch64 shows QEMU, or
# the binary is x86 but uname reports aarch64, etc.
emulated = False
try:
    with open("/proc/cpuinfo") as f:
        cpuinfo = f.read()
    if "QEMU" in cpuinfo.upper():
        emulated = True
except Exception:
    pass
if emulated:
    status("emulation", False, "QEMU detected — expect 5-10× slower startup")
    print("       ↑ pull the native image: docker pull --platform linux/amd64 sidprasad/spytial-clrs")
else:
    status("emulation", True, "none detected")

# ── Resources (what Docker allocated) ────────────────────────────────────────
print("\nResources")
try:
    with open("/proc/meminfo") as f:
        lines = {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in f if ":" in l)}
    total_mb = int(lines["MemTotal"].split()[0]) // 1024
    avail_mb = int(lines["MemAvailable"].split()[0]) // 1024
    ok = avail_mb >= 512
    status("memory", ok, f"{avail_mb} MB available / {total_mb} MB total")
    if not ok:
        print("       ↑ increase Docker memory to ≥2 GB (Docker Desktop → Settings → Resources)")
except Exception:
    status("memory", None, "could not read /proc/meminfo")

cpu_count = os.cpu_count() or 1
status("CPUs", cpu_count >= 2, str(cpu_count))

# ── Startup timing (the actual bottleneck) ───────────────────────────────────
print("\nStartup timing")

# 1) Selenium import — runs on every kernel start via .pth
t0 = time.perf_counter()
try:
    from selenium.webdriver.chrome import webdriver as _cw
    ms = (time.perf_counter() - t0) * 1000
    ok = ms < 5_000
    status("selenium import", ok, f"{ms:.0f} ms")
    if not ok:
        print("       ↑ slow import adds to kernel startup; likely emulation overhead")
except Exception as e:
    status("selenium import", False, str(e))

# 2) Full kernel roundtrip — this is what nbconvert waits for
print("\n  Measuring kernel startup (this may take a moment)...")
t0 = time.perf_counter()
try:
    result = subprocess.run(
        [
            "jupyter", "nbconvert", "--to", "notebook", "--execute",
            "--ExecutePreprocessor.timeout=30",
            "--stdin",
        ],
        input='{"cells":[],"metadata":{"kernelspec":{"name":"python3","display_name":"Python 3","language":"python"}},"nbformat":4,"nbformat_minor":5}',
        capture_output=True, text=True, timeout=120,
    )
    elapsed = time.perf_counter() - t0
    ok = result.returncode == 0 and elapsed < 300
    status("kernel roundtrip", ok, f"{elapsed:.1f} s")
    if elapsed >= 300:
        print("       ↑ kernel takes ≥5 min to start — perf benchmarks will fail")
        print("         this is likely due to emulation or low memory")
    elif elapsed >= 60:
        status("kernel roundtrip", None, f"{elapsed:.1f} s — slow but within 5 min timeout")
    if result.returncode != 0 and result.stderr:
        for line in result.stderr.strip().splitlines()[-3:]:
            print(f"       {line}")
except subprocess.TimeoutExpired:
    status("kernel roundtrip", False, "timed out after 120 s")
    print("       ↑ kernel cannot start in time — check Docker resource allocation")
except Exception as e:
    status("kernel roundtrip", False, str(e))

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
