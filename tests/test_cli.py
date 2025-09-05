"""Unit tests for spotify_playlist.cli orchestrator."""

from __future__ import annotations

from typing import Any, List

import pytest

from spotify_playlist import cli as CLI


class FakeSp:
    def __init__(self, name: str, public: bool) -> None:
        self._name = name
        self._public = public

    def playlist(self, playlist_id: str, fields: str) -> dict:
        return {
            "external_urls": {
                "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
            },
            "name": self._name,
            "public": self._public,
        }


def test_cli_create_from_dr_day_creates_and_adds(monkeypatch, capsys):
    # Mock sources
    monkeypatch.setattr(
        CLI,
        "discover_dr_program_urls",
        lambda s, d, debug=False: [
            "https://dr/one",
            "https://dr/two",
        ],
    )
    monkeypatch.setattr(
        CLI,
        "get_track_queries_from_dr_urls",
        lambda urls, max_tracks=None, debug=False, keep_duplicates=False: [
            "Artist A - Title A",
            "Artist B - Title B",
        ],
    )
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["uri:a", "uri:b"])

    # Mock ops
    created: dict[str, Any] = {}

    def fake_create(sp, name, desc, public):  # noqa: D401
        created.update({"name": name, "public": public})
        return "pl123"

    added: List[str] = []

    def fake_add(sp, plid, uris):  # noqa: D401
        added.extend(uris)

    monkeypatch.setattr(CLI, "create_playlist", fake_create)
    monkeypatch.setattr(CLI, "add_tracks", fake_add)
    monkeypatch.setattr(
        CLI, "get_spotify_client", lambda cache_path=None: FakeSp("MyList", False)
    )

    rc = CLI.main(["-n", "MyList", "--from-dr-day", "p3", "2025-09-05", "-m", "10"])
    captured = capsys.readouterr()
    assert rc == 0
    assert added == ["uri:a", "uri:b"]
    assert "Created private playlist 'MyList' with 2 new tracks:" in captured.out


def test_cli_append_to_name_with_skip_and_retention(monkeypatch, capsys):
    # Prepare mocks
    monkeypatch.setattr(
        CLI, "get_spotify_client", lambda cache_path=None: FakeSp("Existing", True)
    )
    monkeypatch.setattr(CLI, "find_user_playlist_by_name", lambda sp, n: "plid")
    # Two queries -> two URIs
    monkeypatch.setattr(
        CLI,
        "get_track_queries_from_dr_urls",
        lambda *a, **k: [
            "X - Y",
            "A - B",
        ],
    )
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u1", "u2"])

    # Existing playlist has u1 already; only u2 should be added
    monkeypatch.setattr(
        CLI,
        "get_playlist_items_with_meta",
        lambda sp, plid: [{"track": {"uri": "u1"}}],
    )

    removed_calls: list[int] = []
    monkeypatch.setattr(
        CLI,
        "remove_items_older_than",
        lambda sp, plid, days: removed_calls.append(days) or 3,
    )

    added: list[list[str]] = []
    monkeypatch.setattr(CLI, "add_tracks", lambda sp, plid, uris: added.append(uris))

    rc = CLI.main(
        [
            "--append-to-name",
            "Existing",
            "--from-dr-urls",
            "https://dr/program",
            "--skip-existing",
            "--retention-days",
            "7",
            "--debug-scrape",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    # Only one new track added (u2)
    assert added and added[0] == ["u2"]
    assert "Updated public playlist 'Existing' with 1 new tracks:" in captured.out
    assert removed_calls == [7]
    # Debug messages present
    assert "Removed 3 older items" in captured.err
    assert "Skipped 1 tracks already in playlist" in captured.err


def test_cli_from_json_url_requires_keys(monkeypatch, capsys):
    monkeypatch.setattr(
        CLI, "get_spotify_client", lambda cache_path=None: FakeSp("N", False)
    )
    rc = CLI.main(["--from-json-url", "https://example/json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "--json-artist-key" in captured.err


def test_cli_conflicting_append_flags(monkeypatch, capsys):
    monkeypatch.setattr(
        CLI, "get_spotify_client", lambda cache_path=None: FakeSp("N", False)
    )
    # Provide a trivial source so parsing continues to the conflict
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u"])
    rc = CLI.main(
        [
            "--append-to-playlist",
            "plid",
            "--append-to-name",
            "Name",
            "--queries",
            "A - B",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "Use only one of --append-to-playlist or --append-to-name" in captured.err
