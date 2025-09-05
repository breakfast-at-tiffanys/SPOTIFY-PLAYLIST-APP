"""Unit tests for spotify_playlist.sources (pure parts)."""

from __future__ import annotations

from typing import List

from bs4 import BeautifulSoup

from spotify_playlist.sources import (
    discover_dr_program_urls,
)


def test_discover_dr_program_urls_parses_relative_and_absolute(monkeypatch):
    html = (
        '<html><body>'
        '<a href="/lyd/playlister/p3/2025-09-05/foo-abc">x</a>'
        '<a href="https://www.dr.dk/lyd/playlister/p3/2025-09-05/bar-def">y</a>'
        '</body></html>'
    )

    from spotify_playlist import sources as S

    def fake_fetch(url: str) -> str:
        return html

    monkeypatch.setattr(S, "_fetch_html", fake_fetch)
    urls = discover_dr_program_urls("p3", "2025-09-05", debug=False)
    assert urls == [
        "https://www.dr.dk/lyd/playlister/p3/2025-09-05/foo-abc",
        "https://www.dr.dk/lyd/playlister/p3/2025-09-05/bar-def",
    ]


def test_next_data_playlist_points_extraction(monkeypatch):
    # Minimal Next.js payload with two tracks: one via roles, one via description
    payload = {
        "props": {
            "pageProps": {
                "playlistIndexPoints": [
                    {
                        "title": "DAISIES",
                        "roles": [
                            {"role": "Hovedkunstner", "name": "Justin Bieber"}
                        ],
                    },
                    {
                        "title": "Calm Down (Remix)",
                        "description": "Rema og Selena Gomez",
                    },
                ]
            }
        }
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        + __import__("json").dumps(payload)
        + "</script>"
    )
    soup = BeautifulSoup(html, "lxml")

    from spotify_playlist import sources as S

    queries = S._extract_from_next_data_playlist_points(  # type: ignore[attr-defined]
        soup, debug=True, dedupe=True
    )
    assert "Justin Bieber - DAISIES" in queries
    assert "Rema og Selena Gomez - Calm Down (Remix)" in queries

