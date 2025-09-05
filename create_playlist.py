import argparse
import os
import sys
from typing import Iterable, List

from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth


SCOPES = [
    "playlist-modify-private",
    "playlist-modify-public",
    "ugc-image-upload",
]


def get_spotify_client(cache_path: str | None = None) -> Spotify:
    """Authenticate and return a Spotipy client using OAuth.

    Reads credentials from environment variables:
    - SPOTIFY_CLIENT_ID
    - SPOTIFY_CLIENT_SECRET
    - SPOTIFY_REDIRECT_URI
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

    missing = [k for k, v in {
        "SPOTIFY_CLIENT_ID": client_id,
        "SPOTIFY_CLIENT_SECRET": client_secret,
        "SPOTIFY_REDIRECT_URI": redirect_uri,
    }.items() if not v]
    if missing:
        raise SystemExit(
            f"Missing env vars: {', '.join(missing)}.\n"
            "Copy .env.example to .env and fill in your Spotify app credentials."
        )

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SCOPES),
        cache_path=cache_path or ".cache",
        show_dialog=False,
        open_browser=True,
    )
    return Spotify(auth_manager=auth_manager)


def create_playlist(sp: Spotify, name: str, description: str | None, public: bool) -> str:
    me = sp.current_user()
    playlist = sp.user_playlist_create(
        user=me["id"],
        name=name,
        public=public,
        description=description or "",
    )
    return playlist["id"]


def read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def to_batches(items: List[str], size: int = 100) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def resolve_track_uris(sp: Spotify, queries: List[str]) -> List[str]:
    uris: List[str] = []
    for q in queries:
        if q.startswith("spotify:track:") or q.startswith("https://open.spotify.com/track/"):
            uris.append(q)
            continue
        result = sp.search(q, limit=1, type="track")
        items = result.get("tracks", {}).get("items", [])
        if not items:
            print(f"WARN: No match for query: {q}", file=sys.stderr)
            continue
        uris.append(items[0]["uri"])
    return uris


def add_tracks(sp: Spotify, playlist_id: str, uris: List[str]) -> None:
    for chunk in to_batches(uris, 100):
        sp.playlist_add_items(playlist_id, chunk)


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a Spotify playlist from search queries or track URIs.")
    p.add_argument("--name", "-n", required=True, help="Playlist name")
    p.add_argument("--description", "-d", default="", help="Playlist description")
    p.add_argument("--public", action="store_true", default=os.getenv("DEFAULT_PUBLIC", "false").lower() == "true",
                   help="Create as public playlist (default from DEFAULT_PUBLIC)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", "-f", help="Path to text file with one query or URI per line")
    src.add_argument("--queries", "-q", nargs="+", help="One or more search queries/URIs")
    p.add_argument("--cache", default=None, help="Path to Spotipy token cache file (default .cache)")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])

    sp = get_spotify_client(cache_path=args.cache)

    # Gather inputs
    if args.file:
        queries = read_lines(args.file)
    else:
        queries = args.queries

    if not queries:
        print("No queries or URIs provided.", file=sys.stderr)
        return 2

    uris = resolve_track_uris(sp, queries)
    if not uris:
        print("No valid tracks resolved from inputs.", file=sys.stderr)
        return 3

    playlist_id = create_playlist(sp, args.name, args.description, args.public)
    add_tracks(sp, playlist_id, uris)
    playlist = sp.playlist(playlist_id, fields="external_urls.spotify,name,public")

    url = playlist["external_urls"]["spotify"]
    visibility = "public" if playlist["public"] else "private"
    print(f"Created {visibility} playlist '{playlist['name']}' with {len(uris)} tracks: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

