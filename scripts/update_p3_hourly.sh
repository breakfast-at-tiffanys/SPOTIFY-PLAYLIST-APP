#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR%/scripts}"
cd "$REPO_DIR"

if command -v git >/dev/null 2>&1; then
  git pull --ff-only || true
fi

if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

DESC_FILE="playlist-description.txt"
DESC_ARG=""
if [ -f "$DESC_FILE" ]; then
  # shellcheck disable=SC2002
  DESC_ARG="-d \"$(cat "$DESC_FILE")\""
fi

eval python create_playlist.py \
  --append-to-name "P3 (Updated hourly)" \
  --from-dr-day p3 today \
  --processed-urls-file processed_urls.txt \
  --image-path "DRP3_logo.jpeg" \
  ${DESC_ARG} \
  --keep-duplicates --skip-existing --retention-days 7 -m 300
