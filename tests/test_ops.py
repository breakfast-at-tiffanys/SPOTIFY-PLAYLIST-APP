"""Unit tests for spotify_playlist.ops functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List

from spotify_playlist.ops import (
    add_tracks,
    find_user_playlist_by_name,
    remove_items_older_than,
)


class FakeSp:
    def __init__(self) -> None:
        self.add_calls: List[List[str]] = []
        self.remove_calls: List[list[dict[str, Any]]] = []
        self._items: list[dict[str, Any]] = []
        self._playlists_pages: list[list[dict[str, Any]]] = []
        self._next_index = 0

    # Ops helpers
    def playlist_add_items(self, playlist_id: str, chunk: list[str]) -> None:  # noqa: D401
        self.add_calls.append(chunk)

    def playlist_items(
        self, playlist_id: str, limit: int, offset: int, fields: str
    ) -> dict:
        next_url = None
        if offset + limit < len(self._items):
            next_url = "next"
        return {
            "items": self._items[offset : offset + limit],
            "next": next_url,
            "total": len(self._items),
        }

    def playlist_remove_specific_occurrences_of_items(
        self, playlist_id: str, chunk: list[dict[str, Any]]
    ) -> None:
        self.remove_calls.append(chunk)

    # Playlist discovery helpers
    def current_user(self) -> dict:
        return {"id": "me"}

    def current_user_playlists(self, limit: int, offset: int) -> dict:
        page = []
        if self._next_index < len(self._playlists_pages):
            page = self._playlists_pages[self._next_index]
            self._next_index += 1
        next_url = "next" if self._next_index < len(self._playlists_pages) else None
        return {"items": page, "next": next_url}


def test_add_tracks_batches_calls() -> None:
    sp = FakeSp()
    uris = [f"spotify:track:{i}" for i in range(205)]
    add_tracks(sp, "plid", uris)
    assert len(sp.add_calls) == 3
    assert len(sp.add_calls[0]) == 100
    assert len(sp.add_calls[1]) == 100
    assert len(sp.add_calls[2]) == 5


def test_remove_items_older_than_removes_by_positions() -> None:
    sp = FakeSp()
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    recent = (now - timedelta(days=2)).isoformat()
    # Two older occurrences of same uri, one recent different uri
    sp._items = [
        {"added_at": old, "track": {"uri": "u1", "type": "track", "is_local": False}},
        {"added_at": old, "track": {"uri": "u1", "type": "track", "is_local": False}},
        {"added_at": recent, "track": {"uri": "u2", "type": "track", "is_local": False}},
    ]
    removed = remove_items_older_than(sp, "plid", days=7)
    # two positions removed
    assert removed == 2
    assert len(sp.remove_calls) == 1
    payload = sp.remove_calls[0]
    # Ensure positions correspond to indices 0 and 1 for uri u1
    assert any(p["uri"] == "u1" and p["positions"] == [0, 1] for p in payload)


def test_find_user_playlist_by_name_prefers_owned() -> None:
    sp = FakeSp()
    # Page 1 has a non-owned exact match; page 2 has an owned case-insensitive match
    sp._playlists_pages = [
        [
            {"name": "Test", "id": "id1", "owner": {"id": "other"}},
            {"name": "Other", "id": "idx", "owner": {"id": "me"}},
        ],
        [
            {"name": "test", "id": "id2", "owner": {"id": "me"}},
        ],
    ]
    from spotify_playlist.ops import find_user_playlist_by_name

    found = find_user_playlist_by_name(sp, "Test")
    # Prefers owned (id2) over non-owned exact (id1)
    assert found == "id2"

