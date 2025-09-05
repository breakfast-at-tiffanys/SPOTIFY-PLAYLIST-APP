# Spotify Playlist App (Python CLI)

Create Spotify playlists from Python using Spotipy. Provide a list of search queries or track URLs/URIs and this tool creates a playlist and adds the tracks.

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

Provide input as either a text file with one line per query/URI, or pass queries directly.

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
- The script resolves free-text queries to the top search result. If you need precise versions, use Spotify track URLs/URIs.
- Rate limits: adding tracks is batched to 100 per request to respect API limits.

## Troubleshooting

- Redirect URI mismatch: Ensure the URI in `.env` matches the one set in the Spotify Dashboard.
- Token/cache issues: delete the `.cache` file (or your custom cache) and retry.
- No results for a query: the script logs a warning and skips that line.

## Next steps (optional)

- Add support for reading CSV, exporting from other services, or enriching metadata.
- Add cover image upload (supported via `ugc-image-upload`).
- Save the created playlist ID/URL to a file for automation.
