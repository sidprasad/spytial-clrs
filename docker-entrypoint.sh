#!/bin/bash
set -e

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
