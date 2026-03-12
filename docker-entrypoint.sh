#!/bin/bash
set -e

show_help() {
    cat <<'EOF'
Usage: docker run [OPTIONS] spytial-clrs [COMMAND]

SpyTial CLRS — Interactive data structure notebooks & perf benchmarks.

Commands:
  (default)                  Start JupyterLab on port 8888
  --perf <target> [target…]  Run performance benchmarks and output JSON results
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

  docker run -v $(pwd)/results:/app/results spytial-clrs --perf all
      Run all benchmarks; results appear in ./results/

  docker run -v $(pwd)/results:/app/results spytial-clrs --perf trees heaps
      Run benchmarks for trees.ipynb and heaps.ipynb only

  docker run -v $(pwd)/results:/app/results spytial-clrs --perf hash_table_chaining
      Run benchmarks for the notebook containing hash_table_chaining
EOF
}

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
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
