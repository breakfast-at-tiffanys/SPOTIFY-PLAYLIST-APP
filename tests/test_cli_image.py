"""Tests for playlist image upload on creation."""

from __future__ import annotations

from spotify_playlist import cli as CLI


class ImgSp:
    def __init__(self) -> None:
        self.cover_calls: list[tuple[str, str]] = []

    def current_user(self) -> dict:
        return {"id": "me"}

    def user_playlist_create(
        self, user: str, name: str, public: bool, description: str
    ) -> dict:  # noqa: D401,E501
        return {"id": "pl123"}

    def playlist(self, playlist_id: str, fields: str) -> dict:
        return {
            "external_urls": {
                "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
            },
            "name": "N",
            "public": False,
        }

    # image upload
    def playlist_upload_cover_image(
        self, playlist_id: str, image_b64: str
    ) -> None:  # noqa: D401,E501
        self.cover_calls.append((playlist_id, image_b64[:10]))


def test_cli_sets_cover_image_on_create(tmp_path, monkeypatch, capsys):
    # Create a small dummy jpeg-like file (doesn't need real JPEG for the test)
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"\xff\xd8dummy-jpeg\xff\xd9")

    sp = ImgSp()
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: sp)
    # Minimal source: direct queries
    monkeypatch.setattr(
        CLI, "resolve_track_uris", lambda spc, qs: ["u1"]
    )  # noqa: ARG005
    monkeypatch.setattr(CLI, "add_tracks", lambda spc, plid, uris: None)  # noqa: ARG005

    rc = CLI.main(
        [
            "-n",
            "With Image",
            "--image-path",
            str(img),
            "--queries",
            "A - B",
        ]
    )
    capsys.readouterr()
    assert rc == 0
    # Image upload was attempted
    assert sp.cover_calls and sp.cover_calls[0][0] == "pl123"


def test_cli_cover_upload_warn_append_to_name(tmp_path, monkeypatch, capsys):
    # Prepare minimal image file (exists but handler will raise)
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"\xff\xd8dummy-jpeg\xff\xd9")

    sp = ImgSp()
    # Use append-to-name path where playlist is created
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: sp)
    monkeypatch.setattr(CLI, "find_user_playlist_by_name", lambda spc, n: None)
    monkeypatch.setattr(CLI, "create_playlist", lambda spc, n, d, pub: "pl123")
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda spc, qs: ["u1"])  # noqa: ARG005
    monkeypatch.setattr(CLI, "add_tracks", lambda spc, plid, uris: None)  # noqa: ARG005
    # Force upload to raise to hit warn path
    import spotify_playlist.ops as OPS

    monkeypatch.setattr(
        OPS, "upload_playlist_image", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad"))
    )

    rc = CLI.main(
        [
            "--append-to-name",
            "With Warn",
            "--image-path",
            str(img),
            "--queries",
            "A - B",
            "--debug-scrape",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0 and "WARN: Failed to upload cover image" in captured.err


def test_cli_cover_upload_warn_name_create(tmp_path, monkeypatch, capsys):
    # Prepare minimal image file
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"\xff\xd8dummy-jpeg\xff\xd9")

    sp = ImgSp()
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: sp)
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda spc, qs: ["u1"])  # noqa: ARG005
    monkeypatch.setattr(CLI, "add_tracks", lambda spc, plid, uris: None)  # noqa: ARG005
    # Force upload to raise to hit warn path in name-create branch
    import spotify_playlist.ops as OPS

    monkeypatch.setattr(
        OPS, "upload_playlist_image", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )

    rc = CLI.main(
        [
            "-n",
            "ListName",
            "--image-path",
            str(img),
            "--queries",
            "A - B",
            "--debug-scrape",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0 and "WARN: Failed to upload cover image" in captured.err


def test_cli_append_processed_urls_warn(monkeypatch, capsys, tmp_path):
    sp = ImgSp()
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: sp)
    # Discover 1 fresh URL
    monkeypatch.setattr(CLI, "discover_dr_program_urls", lambda *a, **k: ["https://dr/one"])
    monkeypatch.setattr(
        CLI, "get_track_queries_from_dr_urls", lambda *a, **k: ["AR - TT"]
    )
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda spc, qs: ["u1"])  # noqa: ARG005
    monkeypatch.setattr(CLI, "add_tracks", lambda *a, **k: None)
    # Make processed file exist (but contents don't matter)
    processed = tmp_path / "proc.txt"
    processed.write_text("", encoding="utf-8")
    # Force append to processed URLs to raise to hit warn path
    monkeypatch.setattr(CLI, "_append_processed_urls", lambda *a, **k: (_ for _ in ()).throw(IOError("disk")))

    rc = CLI.main(
        [
            "-n",
            "X",
            "--from-dr-day",
            "p3",
            "today",
            "--processed-urls-file",
            str(processed),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0 and "WARN: Failed to update processed URLs file" in captured.err


def test_cli_processed_helpers(monkeypatch, tmp_path):
    # _load_processed_urls returns from try branch with set content
    p = tmp_path / "seen.txt"
    p.write_text("https://a\nhttps://b\n\n", encoding="utf-8")
    out = CLI._load_processed_urls(str(p))  # type: ignore[attr-defined]
    assert out == {"https://a", "https://b"}
    # _append_processed_urls returns early on empty list
    q = tmp_path / "append.txt"
    CLI._append_processed_urls(str(q), [])  # type: ignore[attr-defined]
    assert not q.exists()
