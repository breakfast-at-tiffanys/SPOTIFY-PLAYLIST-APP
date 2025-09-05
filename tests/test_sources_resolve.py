"""Tests for resolve_track_uris search logic with mocked Spotipy."""

from __future__ import annotations

from typing import Any, Dict, List

from spotify_playlist.sources import resolve_track_uris


class FakeSearchSp:
    def __init__(self, results: Dict[str, List[str]]) -> None:
        # maps query -> list of URIs
        self.results = results

    def search(self, q: str, limit: int, type: str) -> dict:  # noqa: A003
        uris = self.results.get(q, [])
        items = [{"uri": u} for u in uris]
        return {"tracks": {"items": items}}


def test_resolve_track_uris_passes_through_track_uri() -> None:
    sp = FakeSearchSp({})
    uris = resolve_track_uris(
        sp,
        [
            "spotify:track:123",
            "https://open.spotify.com/track/abc",
        ],
    )
    assert uris == ["spotify:track:123", "https://open.spotify.com/track/abc"]


def test_resolve_track_uris_structured_then_fallback() -> None:
    # First try structured: track:"Title" artist:"Artist"
    structured = 'track:"Title" artist:"Artist"'
    plain = "Artist - Title"
    sp = FakeSearchSp(
        {
            structured: ["uri:ok"],
        }
    )
    out = resolve_track_uris(sp, [plain])
    assert out == ["uri:ok"]


def test_resolve_track_uris_plain_search_if_structured_missing() -> None:
    structured = 'track:"Title" artist:"Artist"'
    plain = "Artist - Title"
    sp = FakeSearchSp(
        {
            plain: ["uri:plain"],
        }
    )
    out = resolve_track_uris(sp, [plain])
    assert out == ["uri:plain"]
