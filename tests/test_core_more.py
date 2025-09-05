"""Additional tests for spotify_playlist.core."""

from __future__ import annotations

from typing import List

from spotify_playlist.core import (
    dedupe_preserve_order,
    pluck,
    sanitize_query,
    to_batches,
)


def test_to_batches_sizes() -> None:
    items = list(range(0, 250))
    chunks: List[List[int]] = list(to_batches(items, size=100))
    assert [len(c) for c in chunks] == [100, 100, 50]


def test_sanitize_query_removes_brackets_and_bullets() -> None:
    q = "Artist - Title (Live) [2020] • Extra | More"
    out = sanitize_query(q)
    assert out == "Artist - Title"


def test_sanitize_query_blank_returns_none() -> None:
    assert sanitize_query("") is None
    assert sanitize_query("   ") is None
    assert sanitize_query(" - ") is None


def test_pluck_nonexistent_and_invalid_index() -> None:
    data = {"a": [1, 2]}
    assert pluck(data, "a.10") is None
    assert pluck(data, "b.c") is None

