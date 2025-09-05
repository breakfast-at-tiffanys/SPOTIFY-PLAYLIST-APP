"""Even more CLI tests for edge conditions and branches."""

from __future__ import annotations

 

from spotify_playlist import cli as CLI


class BadSp:
    def playlist(self, playlist_id: str, fields: str) -> dict:  # noqa: D401
        raise RuntimeError("not accessible")

    def current_user(self) -> dict:
        return {"id": "me"}


def test_cli_append_to_playlist_inaccessible_returns_4(monkeypatch, capsys):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: BadSp())
    # Provide a trivial source to reach validation
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u"])
    rc = CLI.main(
        [
            "--append-to-playlist",
            "abc123",
            "--queries",
            "A - B",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 4
    assert "Could not access target playlist" in captured.err


def test_cli_from_queries_direct(monkeypatch):
    class OkSp:
        def playlist(self, playlist_id: str, fields: str) -> dict:
            return {
                "external_urls": {
                    "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
                },
                "name": "N",
                "public": False,
            }

    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: OkSp())
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda sp, qs: ["u1", "u2"])
    monkeypatch.setattr(CLI, "create_playlist", lambda sp, n, d, pub: "pl")
    added = []
    monkeypatch.setattr(CLI, "add_tracks", lambda sp, plid, uris: added.extend(uris))
    rc = CLI.main(["-n", "L", "--queries", "A - B", "C - D"])
    assert rc == 0 and added == ["u1", "u2"]
