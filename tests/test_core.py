"""Unit tests for spotify_playlist.core utilities."""

from spotify_playlist.core import (
    dedupe_preserve_order,
    pluck,
    sanitize_query,
)


def test_dedupe_preserve_order():
    assert dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_pluck_with_dict_and_list_indexes():
    data = {"a": {"b": [{"c": 1}, {"c": 2}]}}
    assert pluck(data, "a.b.0.c") == 1
    assert pluck(data, "a.b.1.c") == 2
    assert pluck(data, "a.b.2.c") is None


def test_sanitize_query_artist_title():
    q = "Artist — Title (Remastered) | Extra"
    assert sanitize_query(q) == "Artist - Title"


def test_sanitize_query_long_title_truncates():
    artist = "A"
    title = "x" * 300
    q = f"{artist} - {title}"
    out = sanitize_query(q)
    assert out is not None
    assert len(out) <= 250
