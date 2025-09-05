#!/usr/bin/env bash
set -euo pipefail

# Resolve to repo root (directory of this script's parent)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR%/scripts}"
cd "$REPO_DIR"

# Keep code up to date (non-fatal if remote not configured)
if command -v git >/dev/null 2>&1; then
  git pull --ff-only || true
fi

# Activate venv if present
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

# Run updater for today's date using the name you chose
python create_playlist.py \
  --append-to-name "P3 (Updated daily)" \
  --from-dr-day p3 today \
  --keep-duplicates --skip-existing --retention-days 7 -m 300

