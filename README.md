# Spotify Playlist App (Python CLI)

Automate a rolling Spotify playlist with the songs played on DR P3 each day.
This tool discovers all P3 program playlist pages for a given date, extracts
tracks, resolves them on Spotify, and appends them to your rolling playlist.
It can also remove items older than N days to keep the list fresh.

## Prerequisites

- Python 3.9+
- A Spotify Developer application
  - Create one at https://developer.spotify.com/dashboard
  - Add a Redirect URI (e.g. `http://127.0.0.1:8888/callback`)

## Setup

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

## Usage

Rolling P3 playlist (recommended):

```bash
# One-time (create playlist, make it public)
python create_playlist.py \
  -n "P3 (Updated daily)" \
  --public \
  --image-path DRP3_logo.jpeg \
  -d "$(cat playlist-description.txt)" \
  --from-dr-day p3 $(date +%F) \
  --keep-duplicates --skip-existing --retention-days 7 -m 300

# Daily append (use the playlist by name)
python create_playlist.py \
  --append-to-name "P3 (Updated daily)" \
  --from-dr-day p3 today \
  --image-path DRP3_logo.jpeg \
  -d "$(cat playlist-description.txt)" \
  --keep-duplicates --skip-existing --retention-days 7 -m 300
```

On first run, a browser window opens to authorize the app. After approving, tokens are cached in `.cache` (or your custom `--cache` path).

## Automate on Raspberry Pi

Use cron to run it once per day. Example crontab (runs at 23:59 daily):

```
# Edit with: crontab -e
SHELL=/bin/bash
* 23 * * * cd /home/pi/spotify-playlist-app && \
  /home/pi/spotify-playlist-app/.venv/bin/python create_playlist.py \
  --append-to-name "P3 (Updated daily)" \
  --from-dr-day p3 today \
  --keep-duplicates --skip-existing --retention-days 7 -m 300 \
  >> cron.log 2>&1
```

Or use the helper script (auto git pull + run):

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
  same DR program page multiple times when you run it hourly.
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

## Notes

- Scopes requested:
  - `playlist-modify-private`, `playlist-modify-public`
  - `playlist-read-private`, `playlist-read-collaborative`
  - `ugc-image-upload`, `user-library-read`
- The script resolves free-text queries to the top search result; use Spotify
  track URLs for exact versions.
- Rate limits: tracks are added in batches of 100.

## Troubleshooting

- Redirect URI mismatch: Ensure the URI in `.env` matches your Spotify app.
- Token/cache issues: delete `.cache` (or your `--cache` path) and retry.
- Low track counts: add `--debug-scrape` to see per-URL extraction counts.
