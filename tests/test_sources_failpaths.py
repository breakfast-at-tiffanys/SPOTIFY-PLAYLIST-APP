"""Failure-path and fallback tests for spotify_playlist.sources."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest
from bs4 import BeautifulSoup

from spotify_playlist import sources as S


class FakeResp:
    def __init__(
        self,
        text: str = "",
        data: Any | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.text = text
        self._data = data
        self._raise = raise_exc

    def raise_for_status(self) -> None:  # noqa: D401
        if self._raise is not None:
            raise self._raise

    def json(self) -> Any:  # noqa: D401
        if self._data is None:
            raise ValueError("no json")
        return self._data


def test_resolve_track_uris_skips_empty_and_no_results(monkeypatch):
    class Sp:
        def search(self, q: str, limit: int, type: str) -> dict:  # noqa: A003
            return {"tracks": {"items": []}}

    out = S.resolve_track_uris(Sp(), [" - ", "Artist - X"])  # empty + no results
    assert out == []


def test_get_track_queries_from_json_non_list_returns_empty(monkeypatch):
    payload = {"items": {"not": "a list"}}
    monkeypatch.setattr(
        S.requests, "get", lambda url, timeout=15: FakeResp(data=payload)
    )
    out = S.get_track_queries_from_json(
        url="https://example/json",
        item_path="items",
        artist_key="artist.name",
        title_key="title",
    )
    assert out == []


def test__fetch_html_handles_exception(monkeypatch):
    def bad_get(url: str, headers=None, timeout=20):  # noqa: D401
        raise RuntimeError("network down")

    monkeypatch.setattr(S.requests, "get", bad_get)
    assert S._fetch_html("https://x") is None  # type: ignore[attr-defined]


def test_next_data_invalid_json_returns_empty():
    soup = BeautifulSoup('<script id="__NEXT_DATA__">not json</script>', "lxml")
    out = S._extract_from_next_data_playlist_points(soup)  # type: ignore[attr-defined]
    assert out == []


def test_jsonld_invalid_ignored():
    soup = BeautifulSoup('<script type="application/ld+json">{bad</script>', "lxml")
    out = S._extract_from_jsonld(soup)  # type: ignore[attr-defined]
    assert out == []


def test_orb_cs_fallback(monkeypatch):
    # First request returns short text; second with cs= returns a table
    calls: List[str] = []

    def fake_get(url: str, headers=None, timeout=20):  # noqa: D401
        calls.append(url)
        if "cs=" not in url:
            return FakeResp(text="short")
        html = (
            "<table class='playlist'><tr>"
            "<td class='playlist__artist'>AR</td>"
            "<td class='playlist__title'>TT</td></tr></table>"
        )
        return FakeResp(text=html)

    monkeypatch.setattr(S.requests, "get", fake_get)
    out = S.get_track_queries_from_onlineradiobox(
        "https://onlineradiobox.com/dk/drp3/playlist/"
    )
    assert out == ["AR - TT"]
    assert any("cs=dk.drp3" in u or "/dk/drp3/" in u for u in calls)
