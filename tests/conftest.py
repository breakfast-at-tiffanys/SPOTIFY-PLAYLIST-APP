"""Test configuration to ensure package imports work from the repo root.

Adds the repository root to sys.path so `import spotify_playlist` succeeds
when running pytest in different environments or IDEs.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def _isolate_processed_urls_file(tmp_path, monkeypatch):
    """Ensure tests do not write to the repo's processed_urls.txt.

    By setting PROCESSED_URLS_FILE to a temp path, any CLI invocation that
    relies on the default `--processed-urls-file` uses an isolated file.
    Real runs remain unaffected unless the env var is explicitly set.
    """
    path = tmp_path / "processed_urls.txt"
    monkeypatch.setenv("PROCESSED_URLS_FILE", str(path))
    yield
