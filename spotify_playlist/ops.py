"""Playlist operations: create, add, retention, and lookup by name."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from spotipy import Spotify

from .core import to_batches


def create_playlist(
    sp: Spotify, name: str, description: Optional[str], public: bool
) -> str:
    """Create a playlist for the current user and return its ID.

    Args:
        sp: Spotipy client.
        name: Playlist name.
        description: Optional description.
        public: Whether the playlist is public.

    Returns:
        The new playlist ID.
    """
    me = sp.current_user()
    playlist = sp.user_playlist_create(
        user=me["id"], name=name, public=public, description=description or ""
    )
    return playlist["id"]


def add_tracks(sp: Spotify, playlist_id: str, uris: List[str]) -> None:
    """Add tracks to a playlist in batches of 100.

    Args:
        sp: Spotipy client.
        playlist_id: Target playlist ID.
        uris: Track URIs to add.
    """
    for chunk in to_batches(uris, 100):
        sp.playlist_add_items(playlist_id, chunk)


def get_playlist_items_with_meta(sp: Spotify, playlist_id: str) -> List[dict]:
    """Return playlist items with `added_at` and `track` metadata.

    Args:
        sp: Spotipy client.
        playlist_id: Target playlist ID.

    Returns:
        List of playlist items.
    """
    items: List[dict] = []
    limit = 100
    offset = 0
    fields = "items(added_at,track(uri,type,is_local)),next,total"
    while True:
        resp = sp.playlist_items(
            playlist_id, limit=limit, offset=offset, fields=fields
        )
        chunk = resp.get("items", [])
        if not chunk:
            break
        items.extend(chunk)
        if not resp.get("next"):
            break
        offset += limit
    return items


def remove_items_older_than(sp: Spotify, playlist_id: str, days: int) -> int:
    """Remove occurrences older than `days` based on `added_at` timestamp.

    Args:
        sp: Spotipy client.
        playlist_id: Target playlist ID.
        days: Retention period in days.

    Returns:
        Total number of occurrences removed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = get_playlist_items_with_meta(sp, playlist_id)
    positions_by_uri: dict[str, List[int]] = {}
    for idx, it in enumerate(items):
        added_at = it.get("added_at")
        tr = it.get("track") or {}
        uri = tr.get("uri")
        if not uri or tr.get("type") != "track" or tr.get("is_local"):
            continue
        if not added_at:
            continue
        ts = added_at.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            try:
                dt = datetime.strptime(  # type: ignore[attr-defined]
                    added_at, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except Exception:
                continue
        if dt < cutoff:
            positions_by_uri.setdefault(uri, []).append(idx)
    if not positions_by_uri:
        return 0
    total_removed = 0
    payload = [
        {"uri": uri, "positions": pos}
        for uri, pos in positions_by_uri.items()
    ]
    for chunk in to_batches(payload, 50):
        sp.playlist_remove_specific_occurrences_of_items(playlist_id, chunk)
        total_removed += sum(len(x["positions"]) for x in chunk)
    return total_removed


def find_user_playlist_by_name(sp: Spotify, name: str) -> Optional[str]:
    """Find a playlist ID by name for the current user.

    Prefers an exact match, falling back to case-insensitive match. When there
    are multiple matches, a playlist owned by the current user is preferred.

    Args:
        sp: Spotipy client.
        name: Playlist name to find.

    Returns:
        Playlist ID or None.
    """
    me = sp.current_user()
    user_id = me.get("id")
    limit = 50
    offset = 0
    exact: Optional[str] = None
    ci: Optional[str] = None
    while True:
        resp = sp.current_user_playlists(limit=limit, offset=offset)
        items = resp.get("items", [])
        if not items:
            break
        for pl in items:
            pl_name = pl.get("name") or ""
            pl_id = pl.get("id")
            owner_id = (pl.get("owner") or {}).get("id")
            if pl_name == name:
                if owner_id == user_id:
                    return pl_id
                exact = exact or pl_id
            if pl_name.lower() == name.lower():
                if owner_id == user_id:
                    ci = ci or pl_id
                ci = ci or pl_id
        if resp.get("next"):
            offset += limit
        else:
            break
    return exact or ci

