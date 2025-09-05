"""Compat entrypoint for the refactored Spotify Playlist App.

Keeps original usage working:
    python create_playlist.py [args]

Delegates all logic to spotify_playlist.cli.main.
"""

from spotify_playlist.cli import main  # re-export for exec

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
