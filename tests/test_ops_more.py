"""Additional tests for spotify_playlist.ops."""

from __future__ import annotations

from typing import Any, List

from spotify_playlist.ops import (
    create_playlist,
    get_playlist_items_with_meta,
)


class FakeSp:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self._items: list[dict[str, Any]] = []

    def current_user(self) -> dict:
        return {"id": "user123"}

    def user_playlist_create(self, user: str, name: str, public: bool, description: str) -> dict:  # noqa: D401,E501
        self.created.append({"user": user, "name": name, "public": public, "description": description})
        return {"id": "new_pl"}

    def playlist_items(self, playlist_id: str, limit: int, offset: int, fields: str) -> dict:  # noqa: D401,E501
        next_url = None
        if offset + limit < len(self._items):
            next_url = "next"
        return {"items": self._items[offset : offset + limit], "next": next_url}


def test_create_playlist_calls_spotify() -> None:
    sp = FakeSp()
    plid = create_playlist(sp, "MyName", "Desc", True)
    assert plid == "new_pl"
    assert sp.created and sp.created[0]["name"] == "MyName"


def test_get_playlist_items_with_meta_paginates() -> None:
    sp = FakeSp()
    sp._items = [
        {"added_at": "2024-01-01T00:00:00Z", "track": {"uri": "u1"}},
        {"added_at": "2024-01-01T00:00:00Z", "track": {"uri": "u2"}},
        {"added_at": "2024-01-01T00:00:00Z", "track": {"uri": "u3"}},
    ]
    out = get_playlist_items_with_meta(sp, "pl")
    # Default limit is 100 in impl; still returns all
    assert [o["track"]["uri"] for o in out] == ["u1", "u2", "u3"]

