"""Additional CLI coverage tests focusing on error branches and debug paths."""

from __future__ import annotations

from spotify_playlist import cli as CLI


class DummySp:
    def __init__(self) -> None:  # noqa: D401
        pass

    def playlist(self, playlist_id: str, fields: str) -> dict:  # noqa: D401
        return {
            "external_urls": {
                "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
            },
            "name": "N",
            "public": False,
        }


def test_cli_file_input_no_queries_exit_2(tmp_path, monkeypatch, capsys):
    # Create a file with comments and blanks only
    p = tmp_path / "empty.txt"
    p.write_text("\n# comment\n   \n#another\n", encoding="utf-8")
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    rc = CLI.main(
        ["--file", str(p), "--name", "X"]
    )  # name provided to pass later check
    captured = capsys.readouterr()
    assert rc == 2
    assert "Input file contained no queries." in captured.err


def test_cli_no_valid_tracks_after_resolve_exit_3(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: [])
    rc = CLI.main(["--name", "List", "--queries", "A - B"])  # resolves to empty
    captured = capsys.readouterr()
    assert rc == 3
    assert "No valid tracks resolved from inputs." in captured.err


def test_cli_from_json_url_no_queries_exit_3(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(
        CLI, "get_track_queries_from_json", lambda *a, **k: []  # noqa: D401
    )
    rc = CLI.main(
        [
            "--from-json-url",
            "https://x",
            "--json-artist-key",
            "a",
            "--json-title-key",
            "t",
            "--name",
            "List",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 3
    assert "No queries extracted from JSON source." in captured.err


def test_cli_orb_no_queries_exit_3(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(
        CLI, "get_track_queries_from_onlineradiobox", lambda *a, **k: []
    )
    rc = CLI.main(
        ["--from-onlineradiobox", "https://orb", "--name", "List"]
    )  # noqa: D401
    captured = capsys.readouterr()
    assert rc == 3
    assert "No queries scraped from Onlineradiobox page." in captured.err


def test_cli_dr_urls_no_queries_exit_3(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "get_track_queries_from_dr_urls", lambda *a, **k: [])
    rc = CLI.main(["--from-dr-urls", "https://dr/foo", "--name", "List"])  # noqa: D401
    captured = capsys.readouterr()
    assert rc == 3
    assert "No queries scraped from DR pages." in captured.err


def test_cli_from_dr_day_today_debug_prints(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    # Return two discovered URLs
    urls = ["https://dr/one", "https://dr/two"]
    monkeypatch.setattr(CLI, "discover_dr_program_urls", lambda *a, **k: urls)
    # Each URL yields one query
    monkeypatch.setattr(
        CLI, "get_track_queries_from_dr_urls", lambda u, **k: ["AR - TT", "AR2 - TT2"]
    )
    monkeypatch.setattr(
        CLI, "resolve_track_uris", lambda sp, qs: ["u1", "u2"]
    )  # noqa: E501
    monkeypatch.setattr(CLI, "create_playlist", lambda sp, n, d, pub: "pl")
    monkeypatch.setattr(CLI, "add_tracks", lambda *a, **k: None)
    rc = CLI.main(
        ["-n", "X", "--from-dr-day", "p3", "today", "--debug-scrape"]
    )  # noqa: D401,E501
    captured = capsys.readouterr()
    assert rc == 0
    # Debug should list discovered URLs
    assert "DEBUG: Discovered URL: https://dr/one" in captured.err
    assert "DEBUG: Discovered URL: https://dr/two" in captured.err


def test_cli_append_to_name_creates_and_debug_prints(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "find_user_playlist_by_name", lambda sp, n: None)
    monkeypatch.setattr(
        CLI, "get_track_queries_from_dr_urls", lambda *a, **k: ["A - B"]
    )  # noqa: E501
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u"])  # noqa: D401
    created: list[str] = []
    monkeypatch.setattr(
        CLI, "create_playlist", lambda *a, **k: created.append("ok") or "pl"
    )
    monkeypatch.setattr(CLI, "add_tracks", lambda *a, **k: None)
    rc = CLI.main(
        [
            "--append-to-name",
            "NewList",
            "--from-dr-urls",
            "https://dr/foo",
            "--debug-scrape",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert created  # ensure create_playlist path used
    assert "DEBUG: Created playlist 'NewList'" in captured.err


def test_cli_append_to_playlist_inaccessible_exit_4(monkeypatch, capsys):
    class FailingSp(DummySp):
        def playlist(self, playlist_id: str, fields: str) -> dict:  # noqa: D401
            # First call for access check raises; later call won't be hit
            raise RuntimeError("forbidden")

    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: FailingSp())
    monkeypatch.setattr(
        CLI, "resolve_track_uris", lambda sp, qs: ["u"]
    )  # minimal source
    rc = CLI.main(
        [
            "--append-to-playlist",
            "plid",
            "--queries",
            "A - B",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 4
    assert "Could not access target playlist" in captured.err


def test_cli_name_required_when_not_appending(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u"])  # noqa: D401
    rc = CLI.main(["--queries", "A - B"])  # no --name and not appending
    captured = capsys.readouterr()
    assert rc == 2
    assert "--name is required" in captured.err


def test_cli_file_happy_path(monkeypatch, tmp_path):
    # Valid line should be read and resolved
    p = tmp_path / "in.txt"
    p.write_text("#c\nArtist - Title\n", encoding="utf-8")
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u1"])  # noqa: D401
    monkeypatch.setattr(CLI, "create_playlist", lambda sp, n, d, pub: "pl")
    monkeypatch.setattr(CLI, "add_tracks", lambda *a, **k: None)
    rc = CLI.main(["--file", str(p), "--name", "List"])
    assert rc == 0


def test_cli_from_playlist_and_liked_paths(monkeypatch):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    monkeypatch.setattr(
        CLI, "get_playlist_track_uris", lambda sp, ref, max_tracks=None: ["u"]
    )  # noqa: E501
    monkeypatch.setattr(
        CLI, "get_liked_track_uris", lambda sp, max_tracks=None: ["u"]
    )  # noqa: E501
    monkeypatch.setattr(CLI, "create_playlist", lambda sp, n, d, pub: "pl")
    monkeypatch.setattr(CLI, "add_tracks", lambda *a, **k: None)
    # from-playlist
    rc1 = CLI.main(["--from-playlist", "plid", "--name", "L"])
    # from-liked
    rc2 = CLI.main(["--from-liked", "--name", "L"])
    assert rc1 == 0 and rc2 == 0


def test_cli_from_dr_day_yesterday_and_no_queries_from_pages_exit_3(
    monkeypatch, capsys
):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: DummySp())
    # Discover returns URLs, but scraping yields no queries
    monkeypatch.setattr(
        CLI, "discover_dr_program_urls", lambda *a, **k: ["https://dr/u"]
    )  # noqa: E501
    monkeypatch.setattr(CLI, "get_track_queries_from_dr_urls", lambda *a, **k: [])
    rc = CLI.main(["--from-dr-day", "p3", "yesterday", "--name", "List"])  # noqa: D401
    captured = capsys.readouterr()
    assert rc == 3
    assert "No queries scraped from discovered DR pages." in captured.err


def test_cli_extract_playlist_id_variants():
    assert CLI._extract_playlist_id("spotify:playlist:xyz") == "xyz"
    assert CLI._extract_playlist_id("abc123") == "abc123"
