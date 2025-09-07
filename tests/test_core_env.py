"""Coverage for spotify_playlist.core.get_spotify_client env handling."""

from __future__ import annotations

import spotify_playlist.core as C


def test_get_spotify_client_missing_env_raises(monkeypatch):
    # Clear env vars
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SPOTIFY_REDIRECT_URI", raising=False)
    try:
        C.get_spotify_client(cache_path=None)
        assert False, "Expected SystemExit"
    except SystemExit as e:  # noqa: BLE001
        msg = str(e)
        assert "Missing env vars:" in msg


def test_get_spotify_client_success_monkeypatched(monkeypatch):
    # Provide env vars
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost/callback")

    # Patch SpotifyOAuth and Spotify classes to no-op fakes
    class FakeOAuth:
        def __init__(
            self,
            client_id: str,
            client_secret: str,
            redirect_uri: str,
            scope: str,
            cache_path: str,
            show_dialog: bool,
            open_browser: bool,
        ) -> None:  # noqa: D401
            assert client_id and client_secret and redirect_uri
            assert "playlist-modify-private" in scope
            assert cache_path

    class FakeSpotify:
        def __init__(self, auth_manager: FakeOAuth) -> None:
            self.auth = auth_manager

    monkeypatch.setattr(C, "SpotifyOAuth", FakeOAuth)
    monkeypatch.setattr(C, "Spotify", FakeSpotify)
    sp = C.get_spotify_client(cache_path=".cache.test")
    assert isinstance(sp, FakeSpotify)
