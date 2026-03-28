#!/usr/bin/env bash
set -euo pipefail

# Cron often runs with a minimal PATH.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR%/scripts}"
LOG_FILE="${LOG_FILE:-$REPO_DIR/schedule_run.log}"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG_FILE"
}

resolve_image() {
  if [ -n "${IMAGE:-}" ]; then
    printf '%s\n' "$IMAGE"
    return 0
  fi

  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: IMAGE is not set and git is unavailable for auto-detection." >&2
    return 1
  fi

  local remote repo_path

  remote="$(git -C "$REPO_DIR" config --get remote.origin.url || true)"
  if [ -z "$remote" ]; then
    echo "ERROR: IMAGE is not set and remote.origin.url is unavailable." >&2
    echo "Set IMAGE=ghcr.io/<owner>/<repo>:latest before running the schedule." >&2
    return 1
  fi

  repo_path="${remote%.git}"
  case "$repo_path" in
    git@github.com:*)
      repo_path="${repo_path#git@github.com:}"
      ;;
    https://github.com/*)
      repo_path="${repo_path#https://github.com/}"
      ;;
    http://github.com/*)
      repo_path="${repo_path#http://github.com/}"
      ;;
    ssh://git@github.com/*)
      repo_path="${repo_path#ssh://git@github.com/}"
      ;;
    git://github.com/*)
      repo_path="${repo_path#git://github.com/}"
      ;;
  esac

  if [ "$repo_path" = "$remote" ] || [ "${repo_path#*/}" = "$repo_path" ]; then
    echo "ERROR: Could not infer ghcr image from remote.origin.url='$remote'." >&2
    echo "Set IMAGE=ghcr.io/<owner>/<repo>:latest before running the schedule." >&2
    return 1
  fi

  printf 'ghcr.io/%s:latest\n' "$(printf '%s' "$repo_path" | tr '[:upper:]' '[:lower:]')"
}

main() {
  : > "$LOG_FILE"

  cd "$REPO_DIR"

  if command -v git >/dev/null 2>&1; then
    git pull --ff-only || true
  fi

  export SPOTIFY_BASE_DIR="${SPOTIFY_BASE_DIR:-/opt/spotify}"
  export SPOTIFY_ENV_FILE="${SPOTIFY_ENV_FILE:-$SPOTIFY_BASE_DIR/.env}"
  export DEBUG_SCRAPE="${DEBUG_SCRAPE:-1}"
  export IMAGE="$(resolve_image)"

  log "Scheduled run started"

  if [ ! -f "$SPOTIFY_ENV_FILE" ]; then
    log "ERROR: Environment file not found at '$SPOTIFY_ENV_FILE'."
    exit 1
  fi

  if [ -n "${GHCR_PAT:-}" ] && [ -n "${GHCR_USER:-}" ]; then
    log "Logging in to GHCR"
    printf '%s\n' "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin \
      | tee -a "$LOG_FILE"
  else
    log "Skipping GHCR login (assuming public image)"
  fi

  for path in "$SPOTIFY_BASE_DIR" "$SPOTIFY_BASE_DIR/cache"; do
    if [ -e "$path" ] && [ ! -d "$path" ]; then
      log "ERROR: $path exists but is not a directory."
      ls -l "$path" | tee -a "$LOG_FILE" || true
      exit 1
    fi
  done

  mkdir -p "$SPOTIFY_BASE_DIR/cache"
  touch "$SPOTIFY_BASE_DIR/cache/.cache"
  touch "$SPOTIFY_BASE_DIR/processed_urls.txt"
  chown -R "$(id -un)":"$(id -gn)" "$SPOTIFY_BASE_DIR" 2>>"$LOG_FILE" || true

  {
    echo "== Runner user =="
    whoami
    id
    echo "== Docker versions =="
    docker version || true
    docker compose version || true
    echo "== Resolved variables =="
    echo "IMAGE=$IMAGE"
    echo "SPOTIFY_BASE_DIR=$SPOTIFY_BASE_DIR"
    echo "SPOTIFY_ENV_FILE=$SPOTIFY_ENV_FILE"
    echo "DEBUG_SCRAPE=$DEBUG_SCRAPE"
    echo "== Compose config (with env applied) =="
    docker compose -f deploy/docker-compose.yml config
  } | tee -a "$LOG_FILE"

  {
    echo "== Inspect resolved container command =="
    docker compose -f deploy/docker-compose.yml create app
    cid="$(docker compose -f deploy/docker-compose.yml ps -aq app)"
    if [ -z "${cid:-}" ]; then
      echo "No container ID found after create; showing compose ps -a for context:"
      docker compose -f deploy/docker-compose.yml ps -a || true
    else
      echo "Created container ID: $cid"
      docker inspect "$cid" --format='Entrypoint: {{json .Config.Entrypoint}} Cmd: {{json .Config.Cmd}}'
      docker rm "$cid" >/dev/null 2>&1 || true
    fi
  } | tee -a "$LOG_FILE"

  log "Running docker compose one-shot"
  docker compose -f deploy/docker-compose.yml up --pull=always --abort-on-container-exit \
    2>&1 | tee -a "$LOG_FILE"
  compose_status=${PIPESTATUS[0]}

  {
    echo
    echo "== docker compose ps -a =="
    docker compose -f deploy/docker-compose.yml ps -a || true
    echo
    echo "== docker compose logs --tail=200 =="
    docker compose -f deploy/docker-compose.yml logs --tail=200 || true
  } | tee -a "$LOG_FILE"

  line="$(grep -E "^(Created|Updated) .* playlist '.*' with [0-9]+ new tracks: " -m1 "$LOG_FILE" || true)"
  if [ -n "$line" ]; then
    log "Result: $line"
    num="$(printf '%s\n' "$line" | sed -E 's/.* with ([0-9]+) new tracks:.*/\1/')"
    if [ "$num" = "0" ]; then
      log "WARNING: No new tracks were added in this run (0)."
    fi
  else
    log "Result: No final result line found in logs."
  fi

  discovery="$(grep -E "^DEBUG: Discovered [0-9]+ .*|^DEBUG: New URL:" "$LOG_FILE" || true)"
  counts="$(grep -E "^DEBUG: .* -> (NEXT_DATA|JSON-LD|DOM label|Any-JSON|Regex).*: [0-9]+" "$LOG_FILE" || true)"
  if [ -n "$discovery" ]; then
    {
      echo
      echo "== URL discovery =="
      echo "$discovery"
    } | tee -a "$LOG_FILE"
  fi
  if [ -n "$counts" ]; then
    {
      echo
      echo "== Extraction counts =="
      echo "$counts"
    } | tee -a "$LOG_FILE"
  fi

  if [ "$compose_status" -ne 0 ]; then
    log "Scheduled run failed with exit code $compose_status"
  else
    log "Scheduled run completed successfully"
  fi

  exit "$compose_status"
}

main "$@"
