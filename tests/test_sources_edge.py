"""Edge-case tests for spotify_playlist.sources."""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from spotify_playlist import sources as S


def test_discover_dr_program_urls_regex_fallback(monkeypatch):
    # No <a> tags; only raw text containing links
    html = (
        "Some text https://www.dr.dk/lyd/playlister/p3/2025-09-05/foo "
        "and a relative /lyd/playlister/p3/2025-09-05/bar"
    )

    monkeypatch.setattr(S, "_fetch_html", lambda url: html)
    urls = S.discover_dr_program_urls("p3", "2025-09-05", debug=False)
    assert urls == [
        "https://www.dr.dk/lyd/playlister/p3/2025-09-05/foo",
        "https://www.dr.dk/lyd/playlister/p3/2025-09-05/bar",
    ]


def test_extract_from_dom_labels_basic():
    soup = BeautifulSoup(
        '<div class="track">Artist X - Title Y</div>',
        "lxml",
    )
    out = S._extract_from_dom_labels(soup)  # type: ignore[attr-defined]
    assert out == ["Artist X - Title Y"]


def test_extract_from_regex_strips_time_prefix():
    text = "12:34 Artist A - Title B\nNope\n01:02 C - D"
    out = S._extract_from_regex(text)  # type: ignore[attr-defined]
    assert out == ["Artist A - Title B", "C - D"]


def test_next_data_multiple_artists_and_contributors():
    payload = {
        "props": {
            "pageProps": {
                "playlistIndexPoints": [
                    {
                        "title": "Song",
                        "roles": [
                            {"role": "Hovedkunstner", "name": "A"},
                            {"role": "feature", "name": "B"},
                            {"role": "HOVEDKUNSTNER", "name": "A"},  # duplicate case
                        ],
                    },
                    {
                        "title": "Another",
                        "contributors": [
                            {"role": "artist", "name": "C"},
                            {"role": "composer", "name": "D"},
                        ],
                    },
                ]
            }
        }
    }
    html = '<script id="__NEXT_DATA__">' + json.dumps(payload) + "</script>"
    soup = BeautifulSoup(html, "lxml")
    out = S._extract_from_next_data_playlist_points(  # type: ignore[attr-defined]
        soup, debug=False, dedupe=True
    )
    # First joins and dedupes A,B
    assert "A, B - Song" in out
    # Second uses contributors
    assert "C - Another" in out or "D - Another" in out
