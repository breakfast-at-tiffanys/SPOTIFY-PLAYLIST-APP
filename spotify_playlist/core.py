"""Core utilities and authentication for Spotify Playlist App.

This module defines OAuth scopes, client creation, and helper utilities
for batching, de-duplication, sanitization, and nested key access.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, List, Optional, TypeVar

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

SCOPES: list[str] = [
    # Modify/create playlists
    "playlist-modify-private",
    "playlist-modify-public",
    # Read playlists to support --append-to-name on private or followed lists
    "playlist-read-private",
    "playlist-read-collaborative",
    # Optional extras
    "ugc-image-upload",
    "user-library-read",
]


def get_spotify_client(cache_path: Optional[str] = None) -> Spotify:
    """Authenticate and return a Spotipy client using OAuth.

    Reads environment variables:
    - SPOTIFY_CLIENT_ID
    - SPOTIFY_CLIENT_SECRET
    - SPOTIFY_REDIRECT_URI

    Args:
        cache_path: Path to token cache; defaults to ".cache".

    Returns:
        Authenticated Spotipy client.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

    missing = [
        k
        for k, v in {
            "SPOTIFY_CLIENT_ID": client_id,
            "SPOTIFY_CLIENT_SECRET": client_secret,
            "SPOTIFY_REDIRECT_URI": redirect_uri,
        }.items()
        if not v
    ]
    if missing:
        raise SystemExit(
            "Missing env vars: "
            + ", ".join(missing)
            + ".\nCopy .env.example to .env and fill in your credentials."
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


T = TypeVar("T")


def to_batches(items: List[T], size: int = 100) -> Iterable[List[T]]:
    """Yield `items` in chunks of `size`.

    Args:
        items: Items to chunk.
        size: Chunk size (default 100).

    Yields:
        List slices of at most `size` elements.
    """
    for i in range(0, len(items), size):
        yield items[i: i + size]


def dedupe_preserve_order(items: List[str]) -> List[str]:
    """Remove duplicates while preserving order.

    Args:
        items: Input list.

    Returns:
        New list with first occurrence of each unique item.
    """
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


MAX_QUERY_LEN = 250


def sanitize_query(q: str) -> Optional[str]:
    """Normalize and clamp a free-text query for Spotify search.

    - Collapses whitespace; normalizes en/em dashes to hyphen.
    - If in "Artist - Title" format, trims trailing metadata
      and bracketed segments from the title.
    - Truncates to `MAX_QUERY_LEN`.

    Args:
        q: Raw query.

    Returns:
        Sanitized query or None if empty.
    """
    if not q:
        return None
    q = re.sub(r"[—–]", "-", q)
    q = " ".join(q.split())
    if "-" in q:
        artist, title = q.split("-", 1)
        artist = artist.strip()
        title = title.strip()
        title = re.split(r"\s\|\s|\s•\s|\s-\s", title)[0].strip()
        title = re.sub(r"\s*[\[(].*?[\])]", "", title).strip()
        q = f"{artist} - {title}"
        if len(q) > MAX_QUERY_LEN:
            budget = MAX_QUERY_LEN - (len(artist) + 3)
            title = title[: max(budget, 0)]
            q = f"{artist} - {title}" if budget > 0 else q[:MAX_QUERY_LEN]
    else:
        q = q[:MAX_QUERY_LEN]
    q = q.strip(" -")
    return q or None


def pluck(obj: Any, dotted: str) -> Any:
    """Get a nested value using dot notation, supporting list indexes.

    Args:
        obj: Input dict/list structure.
        dotted: Dot path (e.g., "data.items.0.artist.name").

    Returns:
        The nested value or None.
    """
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur
