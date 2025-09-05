"""Integration-style test using a saved DR playlist page.

This test feeds a downloaded HTML fixture through the DR scraping entrypoint
to validate end-to-end extraction count and output format.
"""

from __future__ import annotations

import re
from pathlib import Path

from spotify_playlist import sources as S


def test_integration_dr_fixture_extraction(monkeypatch):
    # Load the saved DR page fixture (contains 10 playlistIndexPoints)
    fixture_path = Path(__file__).parent / "fixtures" / "dr_program_sample.html"
    html = fixture_path.read_text(encoding="utf-8")

    # Route the fetch to return our downloaded page content
    monkeypatch.setattr(S, "_fetch_html", lambda url: html)

    # Use any URL; content comes from the fixture via monkeypatch
    out = S.get_track_queries_from_dr_urls(["https://www.dr.dk/lyd/playlister/p3/2025-09-05/mock"])

    # Expect exact count and correct format "Artist - Title"
    assert len(out) == 10
    for q in out:
        assert re.match(r"^.+\s-\s.+$", q), f"Bad format: {q}"

    # Spot-check a few specific pairs from the fixture
    assert "Artist A - Song One" in out
    assert "Artist B - Song Two" in out
    assert any(q.startswith("Artist C") and q.endswith("Song Three") for q in out)
    assert "Artist J - Song Ten" in out

