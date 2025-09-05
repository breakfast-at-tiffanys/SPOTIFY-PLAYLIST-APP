"""Extra coverage for sources: resolve without hyphen and debug prints."""

from __future__ import annotations

from spotify_playlist import sources as S


class FakeSp:
    def __init__(self, mapping: dict[str, list[str]]) -> None:  # noqa: D401
        self.mapping = mapping

    def search(self, q: str, limit: int, type: str):  # noqa: A003,D401
        items = [{"uri": u} for u in self.mapping.get(q, [])]
        return {"tracks": {"items": items}}


def test_resolve_track_uris_plain_query_path():
    sp = FakeSp({"Hello": ["uri:hello"]})
    out = S.resolve_track_uris(sp, ["Hello"])  # no ' - '
    assert out == ["uri:hello"]


def test_get_track_queries_from_dr_urls_debug_prints_counts(monkeypatch, capsys):
    # Reuse the saved fixture HTML for DR
    from pathlib import Path

    html = (Path(__file__).parent / "fixtures" / "dr_program_sample.html").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(S, "_fetch_html", lambda url: html)
    out = S.get_track_queries_from_dr_urls(["https://dr/mock"], debug=True)
    assert len(out) >= 1
    captured = capsys.readouterr()
    assert "DEBUG: https://dr/mock -> NEXT_DATA playlistIndexPoints: " in captured.out


def test_discover_dr_program_urls_debug_count(monkeypatch, capsys):
    # Minimal page with two links under the expected base path
    html = (
        "<a href='/lyd/playlister/p3/2025-09-05/one'>x</a>"
        "<a href='/lyd/playlister/p3/2025-09-05/two'>y</a>"
    )
    monkeypatch.setattr(S, "_fetch_html", lambda url: html)
    urls = S.discover_dr_program_urls("p3", "2025-09-05", debug=True)
    assert len(urls) == 2
    captured = capsys.readouterr()
    assert "DEBUG: Discovered 2 DR program URLs for p3 2025-09-05" in captured.out


def test_sources_extract_playlist_id_variants():
    # URL form
    assert (
        S._extract_playlist_id("https://open.spotify.com/playlist/abc123?si=x")
        == "abc123"
    )
    # URI form
    assert S._extract_playlist_id("spotify:playlist:def456") == "def456"
    # Raw ID passthrough
    assert S._extract_playlist_id("rawid") == "rawid"


def test_dr_urls_debug_lines_for_fallback_paths(monkeypatch, capsys):
    # 1) JSON-LD fallback
    import json

    html_jsonld = (
        '<script type="application/ld+json">'
        + json.dumps(
            {
                "@context": "x",
                "byArtist": {"name": "AR"},
                "name": "TT",
            }
        )
        + "</script>"
    )
    monkeypatch.setattr(S, "_fetch_html", lambda url: html_jsonld)
    S.get_track_queries_from_dr_urls(["https://dr/jsonld"], debug=True)
    out = capsys.readouterr()
    assert "JSON-LD matches:" in out.out

    # 2) DOM labels fallback
    html_dom = "<div class='playlist'>Artist X - Title Y</div>"
    monkeypatch.setattr(S, "_fetch_html", lambda url: html_dom)
    S.get_track_queries_from_dr_urls(["https://dr/dom"], debug=True)
    out = capsys.readouterr()
    assert "DOM label matches:" in out.out

    # 3) Any JSON in <script>
    html_any = '<script>var X = {"artist": "AR", "title": "TT"};</script>'
    monkeypatch.setattr(S, "_fetch_html", lambda url: html_any)
    S.get_track_queries_from_dr_urls(["https://dr/any"], debug=True)
    out = capsys.readouterr()
    assert "Any-JSON matches:" in out.out

    # 4) Regex fallback
    html_regex = "<pre>12:34 Artist R - Title S</pre>"
    monkeypatch.setattr(S, "_fetch_html", lambda url: html_regex)
    S.get_track_queries_from_dr_urls(["https://dr/re"], debug=True)
    out = capsys.readouterr()
    assert "Regex matches:" in out.out


def test__fetch_html_success(monkeypatch):
    class FakeResp:
        def __init__(self, text: str) -> None:  # noqa: D401
            self.text = text

        def raise_for_status(self):  # noqa: D401
            return None

    monkeypatch.setattr(
        S.requests, "get", lambda u, headers=None, timeout=20: FakeResp("OK")
    )
    out = S._fetch_html("https://example")
    assert out == "OK"


def test_extract_from_dom_labels_children_path():
    from bs4 import BeautifulSoup

    html = "<div class='playlist'><div><span>Artist K - Title L</span></div></div>"
    soup = BeautifulSoup(html, "lxml")
    out = S._extract_from_dom_labels(soup)
    assert "Artist K - Title L" in out
