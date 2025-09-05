"""Playlist operations: create, add, retention, and lookup by name."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, TypedDict, cast

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
    me = cast(dict[str, Any], sp.current_user())
    user_id = cast(str, me.get("id"))
    playlist = cast(
        dict[str, Any],
        sp.user_playlist_create(
            user=user_id, name=name, public=public, description=description or ""
        ),
    )
    return cast(str, playlist.get("id"))


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
        resp = cast(
            dict[str, Any],
            sp.playlist_items(playlist_id, limit=limit, offset=offset, fields=fields),
        )
        chunk = cast(List[dict], resp.get("items", []))
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
        tr = it.get("track")
        if not isinstance(tr, dict):
            continue
        uri = tr.get("uri")
        if not isinstance(uri, str) or tr.get("type") != "track" or tr.get("is_local"):
            continue
        if not isinstance(added_at, str) or not added_at:
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

    class Occurrence(TypedDict):
        uri: str
        positions: List[int]

    total_removed = 0
    payload: List[Occurrence] = [
        {"uri": uri, "positions": pos} for uri, pos in positions_by_uri.items()
    ]
    for chunk in to_batches(payload, 50):
        sp.playlist_remove_specific_occurrences_of_items(playlist_id, chunk)
        total_removed += sum(len(entry["positions"]) for entry in chunk)
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
    me = cast(dict[str, Any], sp.current_user())
    user_id = cast(Optional[str], me.get("id"))
    limit = 50
    offset = 0
    owned_exact: Optional[str] = None
    owned_ci: Optional[str] = None
    exact: Optional[str] = None
    ci: Optional[str] = None
    while True:
        resp = cast(
            dict[str, Any], sp.current_user_playlists(limit=limit, offset=offset)
        )
        items = cast(List[dict], resp.get("items", []))
        if not items:
            break
        for pl in items:
            pl_name_val = pl.get("name")
            pl_name = pl_name_val if isinstance(pl_name_val, str) else ""
            pl_id_val = pl.get("id")
            pl_id = pl_id_val if isinstance(pl_id_val, str) else None
            owner = pl.get("owner")
            owner_id = owner.get("id") if isinstance(owner, dict) else None
            if pl_name == name:
                if owner_id == user_id and pl_id:
                    owned_exact = owned_exact or pl_id
                else:
                    exact = exact or pl_id
            if pl_name.lower() == name.lower():
                if owner_id == user_id and pl_id:
                    owned_ci = owned_ci or pl_id
                else:
                    ci = ci or pl_id
        if resp.get("next"):
            offset += limit
        else:
            break
    # Preference order: owned exact > owned ci > non-owned exact > non-owned ci
    return owned_exact or owned_ci or exact or ci
