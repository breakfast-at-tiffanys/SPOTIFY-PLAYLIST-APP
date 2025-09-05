"""More tests for spotify_playlist.cli to increase coverage."""

from __future__ import annotations

import pytest

from spotify_playlist import cli as CLI


class DummySp:
    def __init__(self) -> None:
        pass

    def playlist(self, playlist_id: str, fields: str) -> dict:
        return {
            "external_urls": {
                "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
            },
            "name": "N",
            "public": False,
        }


def test_cli_no_input_source_returns_2(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    rc = CLI.main(["-n", "ListName"])  # no source provided
    captured = capsys.readouterr()
    assert rc == 2
    assert "No input source provided." in captured.err


def test_cli_from_json_url_happy_path(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(
        CLI,
        "get_track_queries_from_json",
        lambda u, p, ak, tk, max_tracks=None: ["AR - TT"],
    )
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["uri:1"])
    added = []
    monkeypatch.setattr(CLI, "create_playlist", lambda sp, n, d, pub: "plX")
    monkeypatch.setattr(CLI, "add_tracks", lambda sp, plid, uris: added.extend(uris))
    rc = CLI.main(
        [
            "-n",
            "List",
            "--from-json-url",
            "https://ex/json",
            "--json-item-path",
            "items",
            "--json-artist-key",
            "a",
            "--json-title-key",
            "t",
        ]
    )
    assert rc == 0 and added == ["uri:1"]


def test_cli_from_onlineradiobox_path(monkeypatch):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(
        CLI,
        "get_track_queries_from_onlineradiobox",
        lambda url, max_tracks=None: ["AR - T"],
    )
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u"])
    monkeypatch.setattr(CLI, "create_playlist", lambda sp, n, d, pub: "pl")
    monkeypatch.setattr(CLI, "add_tracks", lambda sp, plid, uris: None)
    rc = CLI.main(["-n", "L", "--from-onlineradiobox", "https://orb"])
    assert rc == 0


def test_cli_from_dr_day_no_urls_exit_3(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "discover_dr_program_urls", lambda *a, **k: [])
    rc = CLI.main(["-n", "L", "--from-dr-day", "p3", "2025-09-05"])
    captured = capsys.readouterr()
    assert rc == 3
    assert "No DR program URLs discovered" in captured.err


def test_cli_append_to_playlist_with_url(monkeypatch):
    # Ensure URL extraction path is covered
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u1", "u2"])
    monkeypatch.setattr(CLI, "add_tracks", lambda sp, plid, uris: None)
    # Provide a trivial source
    rc = CLI.main(
        [
            "--append-to-playlist",
            "https://open.spotify.com/playlist/abc123?si=xyz",
            "--queries",
            "A - B",
        ]
    )
    assert rc == 0
