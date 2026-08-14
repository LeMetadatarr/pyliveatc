#!/usr/bin/env bash
# Launch 4 parallel archive scrapers inside the FlareSolverr container,
# each on a different Xvfb display, processing a facility shard.
#
# Usage:
#   ./launch_archive_scraper.sh HF_TOKEN days [out_dir]
#
# Examples:
#   ./launch_archive_scraper.sh hf_xxx 1           # 1 day, upload to HF
#   ./launch_archive_scraper.sh hf_xxx 3           # 3 days back
#   ./launch_archive_scraper.sh "" 1 /tmp/atc_arc  # local only, no HF

set -euo pipefail

HF_TOKEN="${1:-}"
DAYS="${2:-1}"
OUT_DIR="${3:-/tmp/atc_archive}"
REPO="TigreGotico/liveatc-atc-audio-archive"
CONTAINER="flaresolverr"
SCRIPT="/tmp/archive_scraper.py"

DISPLAYS=(":894762013" ":1370366594" ":1747277545" ":441931107")
N_WORKERS=${#DISPLAYS[@]}  # 4

echo "=== LiveATC Archive Scraper ==="
echo "Workers:   $N_WORKERS"
echo "Days back: $DAYS"
echo "Output:    $OUT_DIR (in container)"
echo "HF repo:   ${HF_TOKEN:+$REPO}"
echo "==============================="

# Copy latest script into container
docker cp "$(dirname "$0")/archive_scraper.py" "$CONTAINER:$SCRIPT"

PIDS=()
for i in "${!DISPLAYS[@]}"; do
    DISPLAY="${DISPLAYS[$i]}"
    SLICE="$i/$N_WORKERS"
    LOG="/tmp/liveatc_worker_${i}.log"

    echo "Starting worker $i/$(($N_WORKERS-1))  DISPLAY=$DISPLAY  slice=$SLICE"

    if [[ -n "$HF_TOKEN" ]]; then
        docker exec \
            -e DISPLAY="$DISPLAY" \
            -e HF_TOKEN="$HF_TOKEN" \
            "$CONTAINER" \
            python3 "$SCRIPT" \
                --hf --repo "$REPO" \
                --out "$OUT_DIR/shard_$i" \
                --days "$DAYS" \
                --slice "$SLICE" \
            > "$LOG" 2>&1 &
    else
        docker exec \
            -e DISPLAY="$DISPLAY" \
            "$CONTAINER" \
            python3 "$SCRIPT" \
                --out "$OUT_DIR/shard_$i" \
                --days "$DAYS" \
                --slice "$SLICE" \
            > "$LOG" 2>&1 &
    fi

    PIDS+=($!)
    echo "  PID: ${PIDS[-1]}  log: $LOG"
done

echo ""
echo "All $N_WORKERS workers started. Monitoring logs:"
echo "  tail -f /tmp/liveatc_worker_*.log"
echo ""
echo "To watch progress:"
echo "  watch -n30 'grep -h OK /tmp/liveatc_worker_*.log | wc -l'"
echo ""
echo "Waiting for all workers to finish..."

FAIL=0
for i in "${!PIDS[@]}"; do
    PID="${PIDS[$i]}"
    if wait "$PID"; then
        echo "Worker $i finished OK"
    else
        echo "Worker $i FAILED (exit $?)"
        FAIL=1
    fi
done

if [[ "$FAIL" -eq 0 ]]; then
    echo "All workers complete."
else
    echo "Some workers failed — check /tmp/liveatc_worker_*.log"
    exit 1
fi
