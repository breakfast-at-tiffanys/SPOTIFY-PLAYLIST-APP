"""Additional unit tests for spotify_playlist.sources.

Covers pagination, JSON mapping, JSON-LD/dom/script extraction, and DR/ORB flows.
"""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

from spotify_playlist import sources as S


class FakeResp:
    def __init__(self, text: str = "", data: Any | None = None) -> None:
        self.text = text
        self._data = data

    def raise_for_status(self) -> None:  # noqa: D401
        return None

    def json(self) -> Any:  # noqa: D401
        if self._data is None:
            raise ValueError("no json")
        return self._data


def test_get_track_queries_from_json_maps_with_item_path(monkeypatch):
    payload = {
        "items": [
            {"artist": {"name": "A"}, "title": "T1"},
            {"artist": {"name": "B"}, "title": "T2"},
        ]
    }

    monkeypatch.setattr(
        S.requests, "get", lambda url, timeout=15: FakeResp(data=payload)
    )
    out = S.get_track_queries_from_json(
        url="https://example/json",
        item_path="items",
        artist_key="artist.name",
        title_key="title",
        max_tracks=None,
    )
    assert out == ["A - T1", "B - T2"]


def test_get_playlist_track_uris_paginates_and_filters():
    class FakeSp:
        def __init__(self) -> None:
            # two pages of items
            self.items = [
                {"track": {"uri": "u1", "type": "track", "is_local": False}},
                {"track": {"uri": "u_local", "type": "track", "is_local": True}},
                {"track": {"uri": "u2", "type": "track", "is_local": False}},
                {"track": {"uri": "not-track", "type": "episode", "is_local": False}},
                {"track": {"uri": "u3", "type": "track", "is_local": False}},
            ]

        def playlist_items(
            self, playlist_id: str, limit: int, offset: int, fields: str
        ):
            next_url = None
            if offset + limit < len(self.items):
                next_url = "next"
            return {
                "items": self.items[offset : offset + limit],
                "next": next_url,
                "total": len(self.items),
            }

    sp = FakeSp()
    uris = S.get_playlist_track_uris(sp, "pl", max_tracks=None)
    assert uris == ["u1", "u2", "u3"]
    # with max_tracks
    sp2 = FakeSp()
    assert S.get_playlist_track_uris(sp2, "pl", max_tracks=2) == ["u1", "u2"]


def test_get_liked_track_uris_paginates_and_filters():
    class FakeSp:
        def __init__(self) -> None:
            self.items = [
                {"track": {"uri": "a1", "type": "track", "is_local": False}},
                {"track": {"uri": "a2", "type": "track", "is_local": False}},
                {"track": {"uri": "x", "type": "episode", "is_local": False}},
            ]

        def current_user_saved_tracks(self, limit: int, offset: int):
            next_chunk = self.items[offset : offset + limit]
            return {"items": next_chunk}

    sp = FakeSp()
    out = S.get_liked_track_uris(
        sp, max_tracks=None  # type: ignore
    )  # pyright: ignore[reportArgumentType]
    assert out == ["a1", "a2"]
    assert S.get_liked_track_uris(sp, max_tracks=1) == ["a1"]  # type: ignore


def test_extract_from_jsonld_parses_artist_and_title():
    obj = {"@context": "x", "byArtist": {"name": "AR"}, "name": "TT"}
    html = '<script type="application/ld+json">' + json.dumps(obj) + "</script>"
    soup = BeautifulSoup(html, "lxml")
    out = S._extract_from_jsonld(soup)  # type: ignore[attr-defined]
    assert out == ["AR - TT"]


def test_extract_from_any_json_scripts_parses_embedded():
    embedded = 'var DATA = {"artist": "AA", "title": "TT" };'  # no type
    soup = BeautifulSoup(f"<script>{embedded}</script>", "lxml")
    out = S._extract_from_any_json_scripts(soup)  # type: ignore[attr-defined]
    assert "AA - TT" in out


def test_onlineradiobox_parses_basic_table(monkeypatch):
    html = (
        "<table class='playlist'><tr><td class='playlist__artist'>AR</td>"
        "<td class='playlist__title'>TT</td></tr>"  # one row
        "<tr><td>Ignored</td></tr></table>"
    )
    monkeypatch.setattr(
        S.requests, "get", lambda u, headers=None, timeout=20: FakeResp(text=html)
    )
    out = S.get_track_queries_from_onlineradiobox("https://orb", max_tracks=None)
    assert out == ["AR - TT"]


def test_get_track_queries_from_dr_urls_aggregate_and_keep_duplicates(monkeypatch):
    payload1 = {
        "props": {
            "pageProps": {
                "playlistIndexPoints": [
                    {
                        "title": "TT1",
                        "roles": [{"role": "Hovedkunstner", "name": "AR1"}],
                    }
                ]
            }
        }
    }
    payload2 = {
        "props": {
            "pageProps": {
                "playlistIndexPoints": [
                    {"title": "TT1", "description": "AR1"},  # duplicate
                    {"title": "TT2", "description": "AR2"},
                ]
            }
        }
    }
    html1 = f'<script id="__NEXT_DATA__">{json.dumps(payload1)}</script>'
    html2 = f'<script id="__NEXT_DATA__">{json.dumps(payload2)}</script>'

    def fake_fetch(url: str) -> str | None:  # noqa: D401
        return html1 if url.endswith("/one") else html2

    monkeypatch.setattr(S, "_fetch_html", fake_fetch)
    urls = ["https://dr/one", "https://dr/two"]
    out = S.get_track_queries_from_dr_urls(urls, keep_duplicates=False)
    # deduped
    assert out == ["AR1 - TT1", "AR2 - TT2"]
    out2 = S.get_track_queries_from_dr_urls(urls, keep_duplicates=True)
    # keeps duplicate AR1 - TT1 from both pages
    assert out2.count("AR1 - TT1") == 2
