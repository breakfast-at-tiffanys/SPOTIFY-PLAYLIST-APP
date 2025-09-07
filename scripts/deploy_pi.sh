#!/usr/bin/env bash
set -euo pipefail

# Deploy this repo to a Raspberry Pi over SSH and set up an hourly systemd timer.
#
# Usage (env vars):
#   PI_USER=pi PI_HOST=raspberrypi.local PI_DIR=/home/pi/spotify-playlist-app \
#   scripts/deploy_pi.sh
#
# Defaults:
#   PI_USER=pi
#   PI_HOST=raspberrypi.local
#   PI_DIR=/home/pi/spotify-playlist-app

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_DIR="${PI_DIR:-/home/pi/spotify-playlist-app}"

if ! command -v ssh >/dev/null 2>&1 || ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: ssh and rsync are required on your machine." >&2
  exit 2
fi

echo "Deploying to ${PI_USER}@${PI_HOST}:${PI_DIR} ..."

# Create target directory
ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" \
  "mkdir -p '${PI_DIR}'"

# Sync files (exclude venv, git, caches, coverage, htmlcov)
rsync -az --delete \
  --exclude '.venv' --exclude '.git' --exclude '__pycache__' \
  --exclude 'htmlcov' --exclude '.coverage*' \
  ./ "${PI_USER}@${PI_HOST}:${PI_DIR}/"

# Install runtime deps and venv on the Pi
ssh "${PI_USER}@${PI_HOST}" bash -lc "set -e; \
  sudo apt-get update -y; \
  sudo apt-get install -y python3-venv python3-pip git; \
  cd '${PI_DIR}'; \
  python3 -m venv .venv; \
  . .venv/bin/activate; \
  pip install --upgrade pip; \
  pip install -r requirements.txt; \
  chmod +x scripts/*.sh || true"

# Install systemd unit + timer
ssh "${PI_USER}@${PI_HOST}" bash -lc "set -e; \
  sudo cp '${PI_DIR}/systemd/p3-playlist.service' /etc/systemd/system/; \
  sudo cp '${PI_DIR}/systemd/p3-playlist.timer' /etc/systemd/system/; \
  sudo systemctl daemon-reload; \
  sudo systemctl enable --now p3-playlist.timer"

echo "Done. Check status with: ssh ${PI_USER}@${PI_HOST} 'systemctl status p3-playlist.timer'"

