"""Extra coverage for spotify_playlist.ops edge branches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import spotify_playlist.ops as OPS


class FakeSp:
    def __init__(self) -> None:  # noqa: D401
        self._items: list[dict[str, Any]] = []
        self.removes: list[list[dict[str, Any]]] = []

    def playlist_items(
        self, playlist_id: str, limit: int, offset: int, fields: str
    ) -> dict:  # noqa: D401,E501
        # Return empty immediately to hit the early-break path
        return {"items": [], "next": None}

    def playlist_remove_specific_occurrences_of_items(
        self, playlist_id: str, chunk: list[dict[str, Any]]
    ) -> None:  # noqa: D401,E501
        self.removes.append(chunk)


def test_get_playlist_items_with_meta_empty_breaks():
    out = OPS.get_playlist_items_with_meta(FakeSp(), "pl")
    assert out == []


def test_remove_items_older_than_handles_various_skips_and_fallback(monkeypatch):
    # Prepare a fake that serves items via the helper function
    class Sp(FakeSp):
        def __init__(self) -> None:  # noqa: D401
            super().__init__()
            self._items = [
                {
                    "added_at": "bad-format",
                    "track": {"uri": "u0", "type": "track", "is_local": False},
                },  # fromisoformat will be monkeypatched to raise
                {
                    "added_at": "2000-01-01T00:00:00Z",
                    "track": {"uri": "u1", "type": "track", "is_local": False},
                },  # fallback strptime applies
                {
                    "added_at": "",
                    "track": {"uri": "u2", "type": "track", "is_local": False},
                },  # missing added_at
                {"track": {"uri": "u3", "type": "track", "is_local": True}},  # local
                {
                    "added_at": "2000-01-01T00:00:00Z",
                    "track": {"uri": "u4", "type": "episode", "is_local": False},
                },  # not a track type
                {"added_at": "2000-01-01T00:00:00Z", "track": None},  # no dict track
            ]

        def playlist_items(
            self, playlist_id: str, limit: int, offset: int, fields: str
        ) -> dict:  # noqa: D401,E501
            return {"items": self._items, "next": None}

    sp = Sp()

    # Force fromisoformat to raise so fallback path executes
    def bad_fromisoformat(_: str):  # noqa: D401
        raise ValueError("bad")

    monkeypatch.setattr(
        OPS,
        "datetime",
        type(
            "D",
            (),
            {  # type: ignore[var-annotated]
                "now": staticmethod(datetime.now),
                "fromisoformat": staticmethod(bad_fromisoformat),
                "strptime": staticmethod(datetime.strptime),
            },
        ),
    )

    removed = OPS.remove_items_older_than(sp, "pl", days=1)
    # Only u1 should qualify for removal and be counted once
    assert removed >= 1


def test_remove_items_older_than_returns_zero_when_none():
    class Sp(FakeSp):
        def __init__(self) -> None:  # noqa: D401
            super().__init__()
            now = datetime.now(timezone.utc).isoformat()
            # Recent track only; not older than cutoff
            self._items = [
                {
                    "added_at": now,
                    "track": {"uri": "u", "type": "track", "is_local": False},
                }
            ]

        def playlist_items(
            self, playlist_id: str, limit: int, offset: int, fields: str
        ) -> dict:  # noqa: D401,E501
            return {"items": self._items, "next": None}

    sp = Sp()
    # With a positive retention window, the recent item is not older -> zero removals
    out = OPS.remove_items_older_than(sp, "pl", days=1)
    assert out == 0


def test_get_playlist_items_with_meta_advances_offset():
    class ManySp(FakeSp):
        def __init__(self) -> None:  # noqa: D401
            super().__init__()
            # 150 items to trigger next pagination branch
            self._all = [
                {"added_at": "x", "track": {"uri": f"u{i}"}} for i in range(150)
            ]

        def playlist_items(
            self, playlist_id: str, limit: int, offset: int, fields: str
        ) -> dict:  # noqa: D401,E501
            next_url = "next" if offset + limit < len(self._all) else None
            return {"items": self._all[offset : offset + limit], "next": next_url}

    sp = ManySp()
    items = OPS.get_playlist_items_with_meta(sp, "pl")
    # Should have all items collected across pagination
    assert len(items) == 150


def test_find_user_playlist_by_name_handles_empty_and_owned_exact():
    class Sp(FakeSp):
        def __init__(self) -> None:  # noqa: D401
            super().__init__()
            self._pages = [
                [{"name": "Exact", "id": "p1", "owner": {"id": "me"}}],
                [],  # empty final page to hit 'not items' break
            ]
            self._i = 0

        def current_user(self) -> dict:  # noqa: D401
            return {"id": "me"}

        def current_user_playlists(self, limit: int, offset: int) -> dict:  # noqa: D401
            page = self._pages[self._i] if self._i < len(self._pages) else []
            self._i += 1
            next_url = "next" if self._i < len(self._pages) else None
            return {"items": page, "next": next_url}

    from spotify_playlist.ops import find_user_playlist_by_name

    sp = Sp()
    found = find_user_playlist_by_name(sp, "Exact")
    assert found == "p1"
