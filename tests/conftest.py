"""Test configuration to ensure package imports work from the repo root.

Adds the repository root to sys.path so `import spotify_playlist` succeeds
when running pytest in different environments or IDEs.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
