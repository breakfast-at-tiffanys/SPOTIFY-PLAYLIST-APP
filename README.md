# Spotify Playlist App (Python CLI)

Create Spotify playlists from Python using Spotipy. Provide a list of search queries or track URLs/URIs — or source tracks from an existing playlist or your Liked Songs — and this tool creates a playlist and adds the tracks.

## Prerequisites

- Python 3.9+
- A Spotify Developer application
  - Create one at https://developer.spotify.com/dashboard
  - Add a Redirect URI (e.g. `http://localhost:8888/callback`)

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

Provide input as either a text file with one line per query/URI, pass queries directly, copy from an existing playlist, pull from Liked Songs, or fetch from a JSON feed (e.g., a station’s recently played endpoint).

Examples:

```bash
# From a file of queries (artist + track names), one per line
python create_playlist.py -n "My Fresh Finds" -f songs.txt

# Direct queries on the command line
python create_playlist.py -n "Gym Mix" -q "The Weeknd - Blinding Lights" "daft punk one more time"

# Mix of direct Spotify URLs and queries
python create_playlist.py -n "Mixed" -q \
  "https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b" \
  "Tame Impala - The Less I Know The Better"

# Create a public playlist
python create_playlist.py -n "Public List" --public -q "nirvana - lithium"

# Copy tracks from an existing playlist (URL/URI/ID)
python create_playlist.py -n "Copied From Discover Weekly" -p https://open.spotify.com/playlist/37i9dQZEVXcFBBexample

# Pull from your Liked Songs (Saved Tracks)
python create_playlist.py -n "My Liked (First 300)" --from-liked -m 300

# Limit number of tracks taken from a source
python create_playlist.py -n "First 100 from X" -p spotify:playlist:4hOKQuZbraPDIfaGbM3lKI -m 100

# From a JSON feed (map fields to artist/title)
# Example keys assume items like: { "artist": {"name": "..."}, "title": "..." }
python create_playlist.py -n "From Feed" \
  --from-json-url https://example.com/recently-played.json \
  --json-item-path items \ 
  --json-artist-key artist.name \
  --json-title-key title \
  -m 50

# Scrape Onlineradiobox station playlist (e.g., DR P3)
python create_playlist.py -n "P3 Latest" \
  --from-onlineradiobox https://onlineradiobox.com/dk/drp3/playlist/ \
  -m 50

# Scrape DR program playlist pages (aggregate multiple URLs for a day)
python create_playlist.py -n "P3 2025-09-05" \
  --from-dr-urls \
  https://www.dr.dk/lyd/playlister/p3/2025-09-05/fredag-5-sep-2025-13332536365 \
  https://www.dr.dk/lyd/playlister/p3/2025-09-05/<another-program-id> \
  https://www.dr.dk/lyd/playlister/p3/2025-09-05/<third-program-id> \
  -m 200

# Auto-discover all DR program pages for a day
python create_playlist.py -n "P3 2025-09-05" \
  --from-dr-day p3 2025-09-05 \
  --keep-duplicates \
  -m 300 --debug-scrape

# Keep a rolling playlist by name (auto-create if missing), remove items older than 7 days
python create_playlist.py \
  --append-to-name "P3 (Updated daily)" \
  --from-dr-day p3 $(date +%F) \
  --keep-duplicates --skip-existing --retention-days 7 -m 300
```

On first run, a browser window opens to authorize the app. After approving, tokens are cached in `.cache` (or your custom `--cache` path).

## Input file format

- One query per line
- Lines starting with `#` are ignored
- Each line can be:
  - A free-text search like `artist - track`
  - A Spotify track URL/URI like `https://open.spotify.com/track/...` or `spotify:track:...`

## Notes

- Scopes requested: `playlist-modify-private`, `playlist-modify-public`, `ugc-image-upload`.
- When using `--from-liked`, add scope `user-library-read` (already configured). You may be prompted to re-authorize once.
- The script resolves free-text queries to the top search result. If you need precise versions, use Spotify track URLs/URIs.
- Rate limits: adding tracks is batched to 100 per request to respect API limits.
- JSON source: use dotted paths for `--json-item-path`, `--json-artist-key`, and `--json-title-key`. Lists can be indexed (e.g., `tracks.0.title`).

## Troubleshooting

- Redirect URI mismatch: Ensure the URI in `.env` matches the one set in the Spotify Dashboard.
- Token/cache issues: delete the `.cache` file (or your custom cache) and retry.
- No results for a query: the script logs a warning and skips that line.

## Next steps (optional)

- Add support for reading CSV, exporting from other services, or enriching metadata.
- Add cover image upload (supported via `ugc-image-upload`).
- Save the created playlist ID/URL to a file for automation.
