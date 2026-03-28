# Spotify Playlist App (Python CLI) 🎧🎶

Automate a rolling Spotify playlist with the songs played on DR P3. 🎵
The app discovers P3 program playlist pages for a date, extracts tracks,
resolves them on Spotify, and appends only new songs to your playlist.
It also removes items older than N days to keep the list fresh.

## Prerequisites 🔑

- Python 3.9+
- A Spotify Developer application
  - Create one at https://developer.spotify.com/dashboard
  - Add a Redirect URI (e.g. `http://127.0.0.1:8888/callback`)

## Setup 🔧

1. Clone or open this folder in your IDE.
2. Copy `.env.example` to `.env` and fill in your credentials:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REDIRECT_URI` (must match your app settings)
3. (Optional) set `DEFAULT_PUBLIC=true` in `.env` if you want public playlists by default.
4. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Minimal Working Example (MVE) 🚀

Create or append to a playlist with a single query (no scraping) — this proves
your credentials and token cache work:

```bash
python create_playlist.py \
  --append-to-name "MVE Test" \
  --queries "Daft Punk - One More Time"
```

On first run, a browser window opens to authorize the app. After approving, tokens are cached in `.cache` (or your custom `--cache` path).

## Rolling P3 Playlist (local Python) 🔁🎵

Append new tracks from today’s P3 pages to a rolling playlist and retain only the last 7 days:

```bash
# First create (public) with cover + description
python create_playlist.py \
  -n "P3 (Updated live)" \
  --public \
  --image-path DRP3_logo.jpeg \
  -d "$(cat playlist-description.txt)" \
  --from-dr-day p3 $(date +%F) \
  --skip-existing --retention-days 7 -m 300

# Subsequent appends by name (today)
python create_playlist.py \
  --append-to-name "P3 (Updated live)" \
  --from-dr-day p3 today \
  --image-path DRP3_logo.jpeg \
  -d "$(cat playlist-description.txt)" \
  --skip-existing --retention-days 7 -m 300
```

## Automate on Raspberry Pi

Use cron to run the Docker-based scheduler every 5 minutes. The host script keeps
the same compose flow as the old GitHub Actions schedule, including env
resolution, persistent file prep, diagnostics, and log parsing.

```
# Edit with: crontab -e
SHELL=/bin/bash
*/5 * * * * cd /home/pi/spotify-playlist-app && \
  /bin/bash ./scripts/run_schedule.sh \
  >> cron.log 2>&1
```

The script writes the latest detailed run log to `schedule_run.log`. It will
auto-detect `IMAGE` from `origin`, or you can export `IMAGE`,
`SPOTIFY_BASE_DIR`, and `SPOTIFY_ENV_FILE` in the crontab if you need overrides.

If you want the schedule to live inside Docker instead of on the Pi host, use
the long-running `scheduler` service:

```bash
mkdir -p /opt/spotify/cache
touch /opt/spotify/cache/.cache /opt/spotify/processed_urls.txt

export IMAGE=ghcr.io/<owner>/<repo>:latest
export SPOTIFY_BASE_DIR=/opt/spotify
export SPOTIFY_ENV_FILE=/opt/spotify/.env

docker compose -f deploy/docker-compose.yml up -d scheduler
docker compose -f deploy/docker-compose.yml logs -f scheduler
```

This keeps a single container running and executes the update every 300 seconds
by default. Override the interval with `SCHEDULE_INTERVAL_SECONDS=600` if you
want a different cadence.

If you prefer a local Python run instead of Docker, use the helper script:

```
chmod +x scripts/update_p3_daily.sh
scripts/update_p3_daily.sh
```

Systemd timer ExecStart can call the script directly:

```
ExecStart=/bin/bash -lc '/home/pi/spotify-playlist-app/scripts/update_p3_daily.sh'
```

Hourly updates with URL de-duplication
- The app now supports a processed-URL state file to avoid reprocessing the
  same DR program page multiple times when you run it repeatedly.
- Use the hourly helper script:

```
chmod +x scripts/update_p3_hourly.sh
scripts/update_p3_hourly.sh
```

- This writes seen URLs to `processed_urls.txt`. You can clear this file if
  you want to force a full reprocess for a day.

- Example systemd timer for hourly runs:

```
[Timer]
OnCalendar=hourly
Persistent=true
```

And set ExecStart to the hourly script:

```
ExecStart=/bin/bash -lc '/home/pi/spotify-playlist-app/scripts/update_p3_hourly.sh'
```

### Deploy via SSH (one command)

Use the deploy script to sync the repo to your Pi, set up a venv, install
dependencies, and install/enable the hourly systemd timer.

```
# From your development machine, with SSH access to the Pi
PI_USER=pi PI_HOST=raspberrypi.local PI_DIR=/home/pi/spotify-playlist-app \
  scripts/deploy_pi.sh
```

Notes:
- Ensure your `.env` and `.cache` exist in the repo root before deploying, or
  copy them to the Pi afterward (`scp .env .cache pi@raspberrypi.local:/home/pi/spotify-playlist-app/`).
- Re-run the deploy script any time you update the code; it will rsync changes
  and keep the timer enabled.

Notes for Pi:
- First run requires authorizing the Spotify app. If headless, you can run the
  tool on a laptop once to generate `.cache`, then copy that file to the Pi.
- If you later change scopes, delete `.cache` and re-authorize once.

## Docker: One‑Shot Runs 🐳

You can run the CLI in Docker. Prepare:

1) `.env` with Spotify credentials (on host)
2) Token file on host (or authenticate once inside the container)
   - Host token path (file): `/path/to/cache/.cache`

Minimal one‑shot (queries):

```bash
docker run --rm \
  --env-file /path/to/.env \
  -v /path/to/cache/.cache:/app/.cache \
  ghcr.io/<owner>/<repo>:latest \
  python -u create_playlist.py \
    --append-to-name "MVE Test" \
    --queries "Daft Punk - One More Time"
```

P3 (today) one‑shot:

```bash
docker run --rm \
  --env-file /path/to/.env \
  -v /path/to/cache/.cache:/app/.cache \
  -v /path/to/processed_urls.txt:/app/processed_urls.txt \
  ghcr.io/<owner>/<repo>:latest \
  python -u create_playlist.py \
    --append-to-name "P3 (Updated live)" \
    --from-dr-day p3 today \
    --image-path DRP3_logo.jpeg \
    --skip-existing --retention-days 7 -m 300
```

First‑time auth in Docker (headless):

```bash
docker run --rm -p 8888:8888 \
  --env-file /path/to/.env \
  -v /path/to/cache/.cache:/app/.cache \
  ghcr.io/<owner>/<repo>:latest \
  python -c "from spotify_playlist.core import get_spotify_client; get_spotify_client(); print('OK')"
```

Open the URL printed by the container and complete the login once. The token is saved to the bound `/path/to/cache/.cache` file.

Docker-native scheduler:

```bash
mkdir -p /path/to/cache
touch /path/to/cache/.cache /path/to/processed_urls.txt

IMAGE=ghcr.io/<owner>/<repo>:latest \
SPOTIFY_BASE_DIR=/path/to \
SPOTIFY_ENV_FILE=/path/to/.env \
SCHEDULE_INTERVAL_SECONDS=300 \
docker compose -f deploy/docker-compose.yml up -d scheduler
```

Watch the scheduler:

```bash
docker compose -f deploy/docker-compose.yml logs -f scheduler
docker compose -f deploy/docker-compose.yml ps
```

## Notes 📌

- Scopes requested:
  - `playlist-modify-private`, `playlist-modify-public`
  - `playlist-read-private`, `playlist-read-collaborative`
  - `ugc-image-upload`, `user-library-read`
- The script resolves free‑text queries to the top search result; provide Spotify
  track URLs/URIs for exact versions.
- Rate limits: tracks are added in batches of 100.

## Troubleshooting 🛠️

- Redirect URI mismatch: Ensure the URI in `.env` matches your Spotify app.
- Token/cache issues: delete `.cache` (or your `--cache` path) and retry.
- Low track counts: add `--debug-scrape` to see per-URL extraction counts.
