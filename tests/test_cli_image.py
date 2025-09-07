"""Tests for playlist image upload on creation."""

from __future__ import annotations

from typing import Any

from spotify_playlist import cli as CLI


class ImgSp:
    def __init__(self) -> None:
        self.cover_calls: list[tuple[str, str]] = []

    def current_user(self) -> dict:
        return {"id": "me"}

    def user_playlist_create(self, user: str, name: str, public: bool, description: str) -> dict:  # noqa: D401,E501
        return {"id": "pl123"}

    def playlist(self, playlist_id: str, fields: str) -> dict:
        return {"external_urls": {"spotify": f"https://open.spotify.com/playlist/{playlist_id}"}, "name": "N", "public": False}

    # image upload
    def playlist_upload_cover_image(self, playlist_id: str, image_b64: str) -> None:  # noqa: D401,E501
        self.cover_calls.append((playlist_id, image_b64[:10]))


def test_cli_sets_cover_image_on_create(tmp_path, monkeypatch, capsys):
    # Create a small dummy jpeg-like file (doesn't need real JPEG for the test)
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"\xff\xd8dummy-jpeg\xff\xd9")

    sp = ImgSp()
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: sp)
    # Minimal source: direct queries
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda spc, qs: ["u1"])  # noqa: ARG005
    monkeypatch.setattr(CLI, "add_tracks", lambda spc, plid, uris: None)  # noqa: ARG005

    rc = CLI.main([
        "-n",
        "With Image",
        "--image-path",
        str(img),
        "--queries",
        "A - B",
    ])
    captured = capsys.readouterr()
    assert rc == 0
    # Image upload was attempted
    assert sp.cover_calls and sp.cover_calls[0][0] == "pl123"

