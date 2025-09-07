"""Negative tests for upload_playlist_image in ops."""

from __future__ import annotations

from pathlib import Path

import pytest

from spotify_playlist.ops import upload_playlist_image


class DummySp:
    def playlist_upload_cover_image(self, playlist_id: str, image_b64: str) -> None:  # noqa: D401,E501
        return None


def test_upload_image_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        upload_playlist_image(DummySp(), "pl", str(tmp_path / "missing.jpg"))


def test_upload_image_too_large(tmp_path):
    big = tmp_path / "big.jpg"
    big.write_bytes(b"\xff\xd8" + b"0" * (256 * 1024 + 1) + b"\xff\xd9")
    with pytest.raises(ValueError):
        upload_playlist_image(DummySp(), "pl", str(big))


def test_upload_image_bad_extension(tmp_path):
    png = tmp_path / "cover.png"
    png.write_bytes(b"not-a-jpeg")
    with pytest.raises(ValueError):
        upload_playlist_image(DummySp(), "pl", str(png))

