"""Tests for the --append-to-name playlist ID cache.

Repeated runs must reuse a previously created/found playlist ID instead of
re-searching by name every time, so a rename or an API pagination miss can't
cause a duplicate playlist to be created on every run.
"""

from __future__ import annotations

import json

from spotify_playlist import cli as CLI


class FakeSp:
    def __init__(self, accessible_ids: set[str]) -> None:
        self._accessible_ids = accessible_ids

    def playlist(self, playlist_id: str, fields: str) -> dict:
        if playlist_id not in self._accessible_ids:
            raise Exception("not found")
        return {
            "external_urls": {
                "spotify": f"https://open.spotify.com/playlist/{playlist_id}"
            },
            "name": "P3 (Updated live)",
            "public": False,
        }


def _run(tmp_path, monkeypatch, sp, cache_path, extra_calls):
    monkeypatch.setattr(CLI, "get_spotify_client", lambda cache_path=None: sp)
    monkeypatch.setattr(CLI, "resolve_track_uris", lambda spc, qs: ["uri:a"])
    monkeypatch.setattr(CLI, "add_tracks", lambda spc, plid, uris: None)
    for name, fn in extra_calls.items():
        monkeypatch.setattr(CLI, name, fn)
    return CLI.main(
        [
            "--append-to-name",
            "P3 (Updated live)",
            "--queries",
            "A - B",
            "--playlist-id-cache",
            str(cache_path),
            "--debug-scrape",
        ]
    )


def test_second_run_reuses_cached_id_without_searching(tmp_path, monkeypatch, capsys):
    cache_path = tmp_path / "playlist_ids.json"
    sp = FakeSp(accessible_ids={"pl-created"})

    search_calls: list[str] = []
    monkeypatch.setattr(
        CLI,
        "find_user_playlist_by_name",
        lambda spc, n: search_calls.append(n) or None,
    )
    monkeypatch.setattr(CLI, "create_playlist", lambda *a, **k: "pl-created")

    rc1 = _run(tmp_path, monkeypatch, sp, cache_path, {})
    assert rc1 == 0
    assert search_calls == ["P3 (Updated live)"]
    assert json.loads(cache_path.read_text()) == {"P3 (Updated live)": "pl-created"}

    capsys.readouterr()
    search_calls.clear()

    def fail_if_called(spc, n):
        raise AssertionError("find_user_playlist_by_name should not be called again")

    def fail_create(*a, **k):
        raise AssertionError("create_playlist should not be called again")

    monkeypatch.setattr(CLI, "find_user_playlist_by_name", fail_if_called)
    monkeypatch.setattr(CLI, "create_playlist", fail_create)

    rc2 = _run(tmp_path, monkeypatch, sp, cache_path, {})
    assert rc2 == 0
    captured = capsys.readouterr()
    assert "Updated private playlist" in captured.out


def test_stale_cached_id_falls_back_to_search(tmp_path, monkeypatch):
    cache_path = tmp_path / "playlist_ids.json"
    cache_path.write_text(json.dumps({"P3 (Updated live)": "deleted-id"}))

    sp = FakeSp(accessible_ids={"found-id"})
    monkeypatch.setattr(CLI, "find_user_playlist_by_name", lambda spc, n: "found-id")
    monkeypatch.setattr(
        CLI,
        "create_playlist",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not create")),
    )

    rc = _run(tmp_path, monkeypatch, sp, cache_path, {})
    assert rc == 0
    assert json.loads(cache_path.read_text()) == {"P3 (Updated live)": "found-id"}
