#!/usr/bin/env bash
set -euo pipefail

# Deploy the containerized "scheduler" service to a Raspberry Pi over SSH.
#
# This is the recommended way to run this app on a Pi: a single long-running
# container that updates the playlist on its own cadence (hourly by
# default), with no host cron and no venv/systemd setup required. It only
# ever brings up the "scheduler" service, never the "oneshot" one, so it
# can't hit the app+scheduler race that used to create duplicate playlists.
#
# Usage (env vars):
#   PI_USER=pi PI_HOST=raspberrypi-1 PI_DIR=/opt/spotify \
#   IMAGE=ghcr.io/<owner>/<repo>:latest \
#   scripts/deploy_pi_docker.sh
#
# Defaults:
#   PI_USER=pi
#   PI_HOST=raspberrypi-1        (Tailscale MagicDNS name; use your own if different)
#   PI_DIR=/opt/spotify
#
# Requires IMAGE to be set (the ghcr.io image built by .github/workflows/deploy.yml).
# Optional: GHCR_USER/GHCR_PAT if the image is private.
#
# Before running this for the first time, put your Spotify credentials in a
# local .env file (see .env.example) - it gets copied to the Pi and never
# committed to git.

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-raspberrypi-1}"
PI_DIR="${PI_DIR:-/opt/spotify}"
ENV_FILE="${ENV_FILE:-.env}"

if [ -z "${IMAGE:-}" ]; then
  echo "ERROR: Set IMAGE=ghcr.io/<owner>/<repo>:latest" >&2
  exit 2
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ERROR: ssh is required on your machine." >&2
  exit 2
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill in your Spotify credentials first." >&2
  exit 2
fi

echo "Deploying to ${PI_USER}@${PI_HOST}:${PI_DIR} (image: ${IMAGE}) ..."

ssh -o StrictHostKeyChecking=accept-new "${PI_USER}@${PI_HOST}" \
  "mkdir -p '${PI_DIR}/deploy' '${PI_DIR}/cache' && \
   touch '${PI_DIR}/cache/.cache' '${PI_DIR}/processed_urls.txt' '${PI_DIR}/playlist_ids.json'"

scp -o StrictHostKeyChecking=accept-new \
  deploy/docker-compose.yml "${PI_USER}@${PI_HOST}:${PI_DIR}/deploy/docker-compose.yml"
scp -o StrictHostKeyChecking=accept-new \
  "$ENV_FILE" "${PI_USER}@${PI_HOST}:${PI_DIR}/.env"

ssh "${PI_USER}@${PI_HOST}" bash -lc "
  set -e
  if ! command -v docker >/dev/null 2>&1; then
    echo 'Installing Docker...'
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker \"\$(whoami)\"
    echo 'Docker installed. You may need to log out/in once for group membership to take effect.'
  fi
"

REMOTE_LOGIN=""
if [ -n "${GHCR_USER:-}" ] && [ -n "${GHCR_PAT:-}" ]; then
  REMOTE_LOGIN="printf '%s' '${GHCR_PAT}' | docker login ghcr.io -u '${GHCR_USER}' --password-stdin"
fi

# A fresh SSH login (as opposed to the shell that just installed Docker
# above) picks up the updated docker group membership, so a plain `docker`
# call works here without needing sudo or a re-login trick.
ssh "${PI_USER}@${PI_HOST}" bash -lc "
  set -e
  cd '${PI_DIR}'
  ${REMOTE_LOGIN}
  export IMAGE='${IMAGE}'
  export SPOTIFY_BASE_DIR='${PI_DIR}'
  export SPOTIFY_ENV_FILE='${PI_DIR}/.env'
  docker compose -f deploy/docker-compose.yml pull scheduler
  docker compose -f deploy/docker-compose.yml up -d scheduler
"

cat <<EOF

Done. The scheduler container updates the playlist hourly by default.

First-time Spotify authorization (only needed once, if ${PI_DIR}/cache/.cache
is empty): the container has no browser, so either:
  1) Authorize once on a laptop, then copy the resulting .cache file:
       scp .cache ${PI_USER}@${PI_HOST}:${PI_DIR}/cache/.cache
  2) Or SSH-tunnel the callback port and authorize from the Pi:
       ssh -L 8888:localhost:8888 ${PI_USER}@${PI_HOST}
       # then on the Pi:
       docker run --rm -it -p 8888:8888 --env-file ${PI_DIR}/.env \\
         -v ${PI_DIR}/cache/.cache:/app/.cache ${IMAGE} \\
         python -c "from spotify_playlist.core import get_spotify_client; get_spotify_client(); print('OK')"
     Open the printed URL in a browser on your laptop and approve.

Check status with:
  ssh ${PI_USER}@${PI_HOST} 'docker compose -f ${PI_DIR}/deploy/docker-compose.yml logs -f scheduler'
EOF
