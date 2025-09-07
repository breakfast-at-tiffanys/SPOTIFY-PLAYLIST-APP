"""Additional coverage for spotify_playlist.sources edge cases."""

from __future__ import annotations

import json

import spotify_playlist.sources as S


def test_get_playlist_track_uris_zero_max_breaks_early():
    class FakeSp:
        def playlist_items(self, *a, **k):  # noqa: D401
            # Should not be called when max_tracks == 0
            raise AssertionError("playlist_items should not be called")

    out = S.get_playlist_track_uris(FakeSp(), "plid", max_tracks=0)  # type: ignore[arg-type]
    assert out == []


def test_get_liked_track_uris_zero_max_breaks_early():
    class FakeSp:
        def current_user_saved_tracks(self, *a, **k):  # noqa: D401
            raise AssertionError("should not fetch when max_tracks == 0")

    out = S.get_liked_track_uris(FakeSp(), max_tracks=0)  # type: ignore[arg-type]
    assert out == []


def test_get_track_queries_from_json_skips_missing_and_respects_max(monkeypatch):
    payload = [
        {"a": {"n": "AR1"}, "t": "T1"},
        {"a": {}, "t": "T2"},  # missing artist name -> skip
        {"a": {"n": "AR3"}},  # missing title -> skip
    ]

    class FakeResp:
        def __init__(self, data):  # noqa: D401
            self._d = data

        def raise_for_status(self):  # noqa: D401
            return None

        def json(self):  # noqa: D401
            return self._d

    monkeypatch.setattr(S.requests, "get", lambda url, timeout=15: FakeResp(payload))
    out = S.get_track_queries_from_json(
        url="https://x",
        item_path=None,
        artist_key="a.n",
        title_key="t",
        max_tracks=1,
    )
    assert out == ["AR1 - T1"]


def test_onlineradiobox_generic_fallback_and_time_strip(monkeypatch):
    # No explicit playlist selectors; forces generic element scan and regex parsing
    html = """
    <html><body>
      <ul>
        <li>12:34 Foo - Bar</li>
        <li>Baz - Quux</li>
      </ul>
    </body></html>
    """

    class FakeResp:
        def __init__(self, text):  # noqa: D401
            self.text = text

        def raise_for_status(self):  # noqa: D401
            return None

    monkeypatch.setattr(S.requests, "get", lambda u, headers=None, timeout=20: FakeResp(html))
    out = S.get_track_queries_from_onlineradiobox("https://orb")
    assert out == ["Foo - Bar", "Baz - Quux"]


def test_extract_from_any_json_scripts_skips_non_json():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<script>var x = 1;</script>", "lxml")
    out = S._extract_from_any_json_scripts(soup)  # type: ignore[attr-defined]
    assert out == []

