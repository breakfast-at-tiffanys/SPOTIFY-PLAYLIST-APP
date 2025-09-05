"""Command-line entrypoint for Spotify Playlist App.

Parses arguments, gathers tracks from sources, applies retention, and
creates or updates a target playlist.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, List, Optional, Set

from dotenv import load_dotenv

from .core import get_spotify_client
from .ops import (
    add_tracks,
    create_playlist,
    find_user_playlist_by_name,
    get_playlist_items_with_meta,
    remove_items_older_than,
)
from .sources import (
    discover_dr_program_urls,
    get_liked_track_uris,
    get_playlist_track_uris,
    get_track_queries_from_dr_urls,
    get_track_queries_from_json,
    get_track_queries_from_onlineradiobox,
    resolve_track_uris,
)


def read_lines(path: str) -> List[str]:
    """Read non-empty, non-comment lines from a text file.

    Args:
        path: File path.

    Returns:
        List of stripped lines.
    """
    with open(path, "r", encoding="utf-8") as fh:
        return [
            line.strip()
            for line in fh
            if line.strip() and not line.strip().startswith("#")
        ]


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Raw argument vector (without program name).

    Returns:
        Parsed arguments namespace.
    """
    p = argparse.ArgumentParser(
        description=("Create or update a Spotify playlist from queries or sources.")
    )
    p.add_argument(
        "--name",
        "-n",
        required=False,
        help="Playlist name (required unless --append-to-* is used)",
    )
    p.add_argument("--description", "-d", default="", help="Playlist description")
    p.add_argument(
        "--public",
        action="store_true",
        default=os.getenv("DEFAULT_PUBLIC", "false").lower() == "true",
        help="Create as public playlist (default from DEFAULT_PUBLIC)",
    )

    # Don't require at parse time so we can return a friendly error code
    src = p.add_mutually_exclusive_group(required=False)
    src.add_argument(
        "--file",
        "-f",
        help="Path to text file with one query or URI per line",
    )
    src.add_argument(
        "--queries",
        "-q",
        nargs="+",
        help="One or more search queries/URIs",
    )
    src.add_argument(
        "--from-playlist",
        "-p",
        help="Source tracks from an existing playlist (URL/URI/ID)",
    )
    src.add_argument(
        "--from-liked",
        action="store_true",
        help="Source tracks from your Liked Songs",
    )
    src.add_argument(
        "--from-json-url",
        help=("Fetch JSON from URL and map to 'artist - title' using dotted keys"),
    )
    src.add_argument(
        "--from-onlineradiobox",
        "-r",
        help="Scrape an Onlineradiobox station playlist URL",
    )
    src.add_argument(
        "--from-dr-urls",
        nargs="+",
        help=(
            "Scrape one or more DR 'lyd' playlist URLs (per-program) and " "aggregate"
        ),
    )
    src.add_argument(
        "--from-dr-day",
        nargs=2,
        metavar=("STATION", "DATE"),
        help=(
            "Discover and scrape all DR playlist program URLs for station "
            "and date (YYYY-MM-DD)"
        ),
    )

    p.add_argument("--json-item-path", default=None, help="Dot path to list in JSON")
    p.add_argument("--json-artist-key", default=None, help="Dotted key for artist")
    p.add_argument("--json-title-key", default=None, help="Dotted key for title")
    p.add_argument(
        "--max-tracks",
        "-m",
        type=int,
        default=None,
        help="Max number of tracks to include from source",
    )
    p.add_argument(
        "--debug-scrape",
        action="store_true",
        help="Print scrape diagnostics (per-URL counts)",
    )
    p.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Keep duplicate 'Artist - Title' entries from source (no dedupe)",
    )
    p.add_argument(
        "--append-to-playlist",
        help="Append to an existing playlist (URL/URI/ID) instead of creating",
    )
    p.add_argument(
        "--append-to-name",
        help="Append to a playlist by name (auto-create if missing)",
    )
    p.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help=(
            "If set, remove items added more than N days ago from target " "playlist"
        ),
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip adding tracks already present in target playlist",
    )
    p.add_argument("--cache", default=None, help="Path to Spotipy token cache file")
    return p.parse_args(argv)


def _extract_playlist_id(s: str) -> str:
    if s.startswith("https://open.spotify.com/playlist/"):
        core = s.split("/playlist/")[-1]
        return core.split("?")[0]
    if s.startswith("spotify:playlist:"):
        return s.split(":")[-1]
    return s


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint.

    Returns:
        Process exit code.
    """
    load_dotenv()
    args = parse_args(argv or sys.argv[1:])
    sp = get_spotify_client(cache_path=args.cache)

    uris: List[str] = []
    if args.file:
        queries = read_lines(args.file)
        if not queries:
            print("Input file contained no queries.", file=sys.stderr)
            return 2
        uris = resolve_track_uris(sp, queries)
    elif args.queries:
        uris = resolve_track_uris(sp, args.queries)
    elif args.from_playlist:
        uris = get_playlist_track_uris(
            sp, args.from_playlist, max_tracks=args.max_tracks
        )
    elif args.from_liked:
        uris = get_liked_track_uris(sp, max_tracks=args.max_tracks)
    elif args.from_json_url:
        if not args.json_artist_key or not args.json_title_key:
            print(
                "--json-artist-key and --json-title-key are required with "
                "--from-json-url",
                file=sys.stderr,
            )
            return 2
        queries = get_track_queries_from_json(
            args.from_json_url,
            args.json_item_path,
            args.json_artist_key,
            args.json_title_key,
            max_tracks=args.max_tracks,
        )
        if not queries:
            print("No queries extracted from JSON source.", file=sys.stderr)
            return 3
        uris = resolve_track_uris(sp, queries)
    elif args.from_onlineradiobox:
        queries = get_track_queries_from_onlineradiobox(
            args.from_onlineradiobox, max_tracks=args.max_tracks
        )
        if not queries:
            print("No queries scraped from Onlineradiobox page.", file=sys.stderr)
            return 3
        uris = resolve_track_uris(sp, queries)
    elif args.from_dr_urls:
        queries = get_track_queries_from_dr_urls(
            args.from_dr_urls,
            max_tracks=args.max_tracks,
            debug=args.debug_scrape,
            keep_duplicates=args.keep_duplicates,
        )
        if not queries:
            print("No queries scraped from DR pages.", file=sys.stderr)
            return 3
        uris = resolve_track_uris(sp, queries)
    elif args.from_dr_day:
        station, date = args.from_dr_day
        urls = discover_dr_program_urls(station, date, debug=args.debug_scrape)
        if not urls:
            print(
                f"No DR program URLs discovered for {station} {date}.",
                file=sys.stderr,
            )
            return 3
        if args.debug_scrape:
            for u in urls:
                print(f"DEBUG: Discovered URL: {u}", file=sys.stderr)
        queries = get_track_queries_from_dr_urls(
            urls,
            max_tracks=args.max_tracks,
            debug=args.debug_scrape,
            keep_duplicates=args.keep_duplicates,
        )
        if not queries:
            print("No queries scraped from discovered DR pages.", file=sys.stderr)
            return 3
        uris = resolve_track_uris(sp, queries)
    else:
        print("No input source provided.", file=sys.stderr)
        return 2

    if not uris:
        print("No valid tracks resolved from inputs.", file=sys.stderr)
        return 3

    # Resolve or create target playlist.
    if args.append_to_playlist and args.append_to_name:
        print(
            "ERROR: Use only one of --append-to-playlist or --append-to-name",
            file=sys.stderr,
        )
        return 2
    if args.append_to_playlist:
        playlist_id = _extract_playlist_id(args.append_to_playlist)
        try:
            sp.playlist(playlist_id, fields="id")
        except Exception as e:  # noqa: BLE001
            print(
                f"ERROR: Could not access target playlist "
                f"{args.append_to_playlist}: {e}",
                file=sys.stderr,
            )
            return 4
    elif args.append_to_name:
        target_name = args.append_to_name
        found_id = find_user_playlist_by_name(sp, target_name)
        if found_id:
            playlist_id = found_id
        else:
            playlist_id = create_playlist(
                sp, target_name, args.description, args.public  # type: ignore
            )
            if args.debug_scrape:
                print(
                    f"DEBUG: Created playlist '{target_name}'",
                    file=sys.stderr,
                )
    else:
        if not args.name:
            print(
                "ERROR: --name is required when not using --append-to-playlist",
                file=sys.stderr,
            )
            return 2
        playlist_id = create_playlist(sp, args.name, args.description, args.public)

    # Apply retention policy first.
    if args.retention_days and args.retention_days > 0:
        removed = remove_items_older_than(sp, playlist_id, args.retention_days)
        if removed and args.debug_scrape:
            print(
                f"DEBUG: Removed {removed} older items (> {args.retention_days} days)",
                file=sys.stderr,
            )

    # Optionally skip adding any already-present tracks.
    if args.skip_existing:
        existing = get_playlist_items_with_meta(sp, playlist_id)
        # Safely collect existing URIs
        existing_uris: Set[str] = set()
        for item in existing:
            track = item.get("track")
            if isinstance(track, dict):
                uri = track.get("uri")
                if isinstance(uri, str):
                    existing_uris.add(uri)
        before = len(uris)
        uris = [u for u in uris if u not in existing_uris]
        skipped = before - len(uris)
        if skipped and args.debug_scrape:
            print(
                f"DEBUG: Skipped {skipped} tracks already in playlist", file=sys.stderr
            )

    if uris:
        add_tracks(sp, playlist_id, uris)

    playlist_obj = sp.playlist(playlist_id, fields="external_urls.spotify,name,public")
    # Safely extract fields for Pylance and robustness
    playlist_dict: Any = playlist_obj if isinstance(playlist_obj, dict) else {}
    ext = (
        playlist_dict.get("external_urls") if isinstance(playlist_dict, dict) else None
    )
    url_val = ext.get("spotify") if isinstance(ext, dict) else None
    url = (
        url_val
        if isinstance(url_val, str)
        else f"https://open.spotify.com/playlist/{playlist_id}"
    )
    public_val = (
        playlist_dict.get("public") if isinstance(playlist_dict, dict) else False
    )
    visibility = "public" if bool(public_val) else "private"
    action = (
        "Updated" if (args.append_to_playlist or args.append_to_name) else "Created"
    )
    print(
        f"{action} {visibility} playlist '{(playlist_dict.get('name') or '')}' with "
        f"{len(uris)} new tracks: {url}"
    )
    return 0
