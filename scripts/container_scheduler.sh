#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR%/scripts}"
cd "$REPO_DIR"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

INTERVAL_SECONDS="${SCHEDULE_INTERVAL_SECONDS:-300}"
PLAYLIST_NAME="${PLAYLIST_NAME:-P3 (Updated live)}"
DR_PROGRAM="${DR_PROGRAM:-p3}"
DR_DAY="${DR_DAY:-today}"
PROCESSED_URLS_FILE="${PROCESSED_URLS_FILE:-processed_urls.txt}"
PLAYLIST_IMAGE_PATH="${PLAYLIST_IMAGE_PATH:-DRP3_logo.jpeg}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
MAX_TRACKS="${MAX_TRACKS:-300}"
SET_IMAGE_ALWAYS="${SET_IMAGE_ALWAYS:-1}"
DEBUG_SCRAPE="${DEBUG_SCRAPE:-1}"

if ! [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [ "$INTERVAL_SECONDS" -le 0 ]; then
  echo "ERROR: SCHEDULE_INTERVAL_SECONDS must be a positive integer." >&2
  exit 2
fi

stop_requested=0

handle_stop() {
  stop_requested=1
  log "Stop requested; exiting after the current run."
}

trap handle_stop INT TERM

run_once() {
  local cmd
  cmd=(
    python -u create_playlist.py
    --append-to-name "$PLAYLIST_NAME"
    --from-dr-day "$DR_PROGRAM" "$DR_DAY"
    --processed-urls-file "$PROCESSED_URLS_FILE"
    --image-path "$PLAYLIST_IMAGE_PATH"
    --skip-existing
    --retention-days "$RETENTION_DAYS"
    -m "$MAX_TRACKS"
  )

  if [ "$SET_IMAGE_ALWAYS" = "1" ]; then
    cmd+=(--set-image-always)
  fi

  if [ "$DEBUG_SCRAPE" = "1" ]; then
    cmd+=(--debug-scrape)
  fi

  if [ -f playlist-description.txt ]; then
    cmd+=(-d "$(cat playlist-description.txt)")
  fi

  log "Starting playlist update"
  "${cmd[@]}"
  log "Playlist update completed"
}

while true; do
  run_started="$(date +%s)"

  if run_once; then
    status=0
  else
    status=$?
    log "Playlist update failed with exit code $status"
  fi

  if [ "$stop_requested" -eq 1 ]; then
    exit "$status"
  fi

  now="$(date +%s)"
  elapsed=$((now - run_started))
  sleep_for=$((INTERVAL_SECONDS - elapsed))
  if [ "$sleep_for" -lt 0 ]; then
    sleep_for=0
  fi

  log "Sleeping ${sleep_for}s before next run"
  sleep "$sleep_for" &
  wait $! || true

  if [ "$stop_requested" -eq 1 ]; then
    exit "$status"
  fi
done
