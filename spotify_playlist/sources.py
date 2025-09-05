"""Track sources and scraping for Spotify Playlist App.

This module provides functions to gather track queries or Spotify URIs from
various sources: existing playlists, liked songs, JSON feeds, DR playlist pages,
and Onlineradiobox station pages.
"""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Protocol, cast
from urllib.parse import (
    parse_qsl,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from spotipy import Spotify

from .core import dedupe_preserve_order, pluck


class SearchClient(Protocol):
    """Minimal interface required for searching tracks.

    Matches Spotipy's search method (with optional params) and allows
    lightweight fakes in tests. Return type is Any and cast at use sites.
    """

    def search(
        self,
        q: str,
        limit: int = ...,  # noqa: D401
        offset: int = ...,
        type: str = ...,  # noqa: A003 - 'type' is Spotipy's param name
        market: Optional[str] = ...,
    ) -> Any: ...


def resolve_track_uris(sp: SearchClient, queries: List[str]) -> List[str]:
    """Resolve a list of search queries/URIs to Spotify track URIs.

    Args:
        sp: Authenticated Spotipy client.
        queries: Free-text queries ("Artist - Title") or track URLs/URIs.

    Returns:
        Resolved Spotify track URIs.
    """
    from .core import sanitize_query  # local import to avoid cycles

    def _search_track(artist: str, title: str) -> Optional[str]:
        for q in [
            f'track:"{title}" artist:"{artist}"',
            f'artist:"{artist}" track:"{title}"',
            f"track:{title} artist:{artist}",
        ]:
            result = cast(dict[str, Any], sp.search(q, limit=1, type="track"))
            tracks = cast(dict[str, Any], result.get("tracks") or {})
            items = cast(List[dict], tracks.get("items") or [])
            if items:
                return items[0]["uri"]
        return None

    uris: List[str] = []
    for q in queries:
        if q.startswith("spotify:track:") or q.startswith(
            "https://open.spotify.com/track/"
        ):
            uris.append(q)
            continue
        q = sanitize_query(q) or ""
        if not q:
            continue
        if " - " in q:
            artist, title = q.split(" - ", 1)
            artist = artist.strip()
            title = title.strip()
            uri = _search_track(artist, title)
            if uri is None:
                res = cast(dict[str, Any], sp.search(q, limit=1, type="track"))
                tracks = cast(dict[str, Any], res.get("tracks") or {})
                items = cast(List[dict], tracks.get("items") or [])
                if items:
                    uri = items[0]["uri"]
            if uri:
                uris.append(uri)
        else:
            res = cast(dict[str, Any], sp.search(q, limit=1, type="track"))
            tracks = cast(dict[str, Any], res.get("tracks") or {})
            items = cast(List[dict], tracks.get("items") or [])
            if items:
                uris.append(items[0]["uri"])
    return uris


def _extract_playlist_id(ref: str) -> str:
    if ref.startswith("https://open.spotify.com/playlist/"):
        core = ref.split("/playlist/")[-1]
        return core.split("?")[0]
    if ref.startswith("spotify:playlist:"):
        return ref.split(":")[-1]
    return ref


def get_playlist_track_uris(
    sp: Spotify, playlist_ref: str, max_tracks: Optional[int] = None
) -> List[str]:
    """Fetch track URIs from an existing playlist, skipping local items.

    Args:
        sp: Spotipy client.
        playlist_ref: URL/URI/ID of the playlist.
        max_tracks: Optional limit.

    Returns:
        List of track URIs.
    """
    playlist_id = _extract_playlist_id(playlist_ref)
    uris: List[str] = []
    limit = 100
    offset = 0
    while True:
        if max_tracks is not None and len(uris) >= max_tracks:
            break
        fields = "items(track(uri,type,is_local)),next,total"
        resp = cast(
            dict[str, Any],
            sp.playlist_items(playlist_id, limit=limit, offset=offset, fields=fields),
        )
        items = cast(List[dict], resp.get("items", []))
        for it in items:
            tr = it.get("track")
            if not tr or tr.get("type") != "track" or tr.get("is_local"):
                continue
            uris.append(tr["uri"])
            if max_tracks is not None and len(uris) >= max_tracks:
                break
        if not resp.get("next") or (max_tracks is not None and len(uris) >= max_tracks):
            break
        offset += limit
    return uris


def get_liked_track_uris(sp: Spotify, max_tracks: Optional[int] = None) -> List[str]:
    """Fetch track URIs from the user's Liked Songs.

    Args:
        sp: Spotipy client.
        max_tracks: Optional limit.

    Returns:
        List of track URIs.
    """
    uris: List[str] = []
    limit = 50
    offset = 0
    while True:
        if max_tracks is not None and len(uris) >= max_tracks:
            break
        resp = cast(
            dict[str, Any],
            sp.current_user_saved_tracks(limit=limit, offset=offset),
        )
        items = cast(List[dict], resp.get("items", []))
        for it in items:
            tr = it.get("track")
            if not tr or tr.get("type") != "track" or tr.get("is_local"):
                continue
            uris.append(tr["uri"])
            if max_tracks is not None and len(uris) >= max_tracks:
                break
        if len(items) < limit or (max_tracks is not None and len(uris) >= max_tracks):
            break
        offset += limit
    return uris


def get_track_queries_from_json(
    url: str,
    item_path: Optional[str],
    artist_key: str,
    title_key: str,
    max_tracks: Optional[int] = None,
) -> List[str]:
    """Fetch JSON from URL and build queries from list items.

    Args:
        url: JSON endpoint.
        item_path: Dot path to the list in JSON (root must be list if None).
        artist_key: Dotted key for artist relative to each item.
        title_key: Dotted key for title relative to each item.
        max_tracks: Optional limit.

    Returns:
        Queries in "Artist - Title" format.
    """
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = pluck(data, item_path) if item_path else data
    if not isinstance(items, list):
        return []
    queries: List[str] = []
    for it in items:
        artist = pluck(it, artist_key) if artist_key else None
        title = pluck(it, title_key) if title_key else None
        if not artist or not title:
            continue
        queries.append(f"{artist} - {title}")
        if max_tracks is not None and len(queries) >= max_tracks:
            break
    return queries


def _fetch_html(url: str) -> Optional[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome Safari"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _json_nodes(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _json_nodes(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _json_nodes(it)


def _extract_from_next_data_playlist_points(
    soup: BeautifulSoup, debug: bool = False, dedupe: bool = True
) -> List[str]:
    script = soup.find("script", id="__NEXT_DATA__")
    if not isinstance(script, Tag):
        return []
    raw_any = script.string if script.string is not None else script.text
    if raw_any is None:
        raw_any = ""
    raw = str(raw_any).strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []

    def artist_from_node(n: dict) -> Optional[str]:
        for k in (
            "artist",
            "artistName",
            "artist_name",
            "primaryArtist",
            "creator",
            "composer",
        ):
            v = n.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                name = v.get("name") or v.get("title") or v.get("text")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        v = n.get("byArtist")
        if isinstance(v, dict):
            name = v.get("name") or v.get("alternateName")
            if isinstance(name, str) and name.strip():
                return name.strip()
        contribs = n.get("contributors") or n.get("contributor")
        if isinstance(contribs, list):
            for c in contribs:
                if not isinstance(c, dict):
                    continue
                role = (c.get("role") or "").lower()
                nm = c.get("name") or c.get("title")
                if (
                    isinstance(nm, str)
                    and nm.strip()
                    and (not role or role in ("artist", "performer", "composer"))
                ):
                    return nm.strip()
        return None

    def title_from_node(n: dict) -> Optional[str]:
        for k in ("trackTitle", "songTitle", "title", "name", "workTitle"):
            v = n.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for k in ("track", "song", "recording", "work"):
            v = n.get(k)
            if isinstance(v, dict):
                t = v.get("title") or v.get("name")
                if isinstance(t, str) and t.strip():
                    return t.strip()
        return None

    def collect_points(obj: Any) -> List[Any]:
        points: List[Any] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "playlistIndexPoints" and isinstance(v, list):
                    points.extend(v)
                else:
                    points.extend(collect_points(v))
        elif isinstance(obj, list):
            for it in obj:
                points.extend(collect_points(it))
        return points

    points = collect_points(data)
    queries: List[str] = []
    for pt in points:
        if not isinstance(pt, (dict, list)):
            continue
        # Always operate on dict nodes
        nodes: List[dict] = []
        if isinstance(pt, dict):
            nodes.append(pt)
        nodes.extend([n for n in _json_nodes(pt) if isinstance(n, dict)])
        artist: Optional[str] = None
        title: Optional[str] = None
        for n in nodes:
            if artist is None:
                roles = n.get("roles") if isinstance(n, dict) else None
                if isinstance(roles, list) and roles:
                    names: List[str] = []
                    for r in roles:
                        if not isinstance(r, dict):
                            continue
                        role = (r.get("role") or "").lower()
                        if role in (
                            "hovedkunstner",
                            "main",
                            "artist",
                            "performer",
                            "feature",
                            "primary artist",
                            "primary_artist",
                            "primaryartist",
                        ):
                            nm = r.get("name")
                            if isinstance(nm, str) and nm.strip():
                                names.append(nm.strip())
                    if names:
                        artist = ", ".join(dedupe_preserve_order(names))
                if artist is None and isinstance(n, dict):
                    roles = n.get("roles")
                    if isinstance(roles, list) and roles:
                        names = []
                        for r in roles:
                            if isinstance(r, dict):
                                nm = r.get("name")
                                if isinstance(nm, str) and nm.strip():
                                    names.append(nm.strip())
                        if names:
                            artist = ", ".join(dedupe_preserve_order(names))
                if artist is None and isinstance(n, dict):
                    artist = artist_from_node(n)
            if title is None:
                t = title_from_node(n) if isinstance(n, dict) else None
                if not t and isinstance(n, dict):
                    cand = n.get("title") or n.get("name")
                    if isinstance(cand, str) and cand.strip():
                        t = cand.strip()
                title = t
            if artist and title:
                break
        if not artist and isinstance(pt, dict):
            desc = pt.get("description")
            if isinstance(desc, str) and desc.strip():
                artist = desc.strip()
        if artist and title:
            queries.append(f"{artist} - {title}")
    return dedupe_preserve_order(queries) if dedupe else queries


def get_track_queries_from_onlineradiobox(
    url: str, max_tracks: Optional[int] = None
) -> List[str]:
    """Scrape an Onlineradiobox station playlist page for recent tracks.

    Args:
        url: Station playlist URL.
        max_tracks: Optional limit.

    Returns:
        Queries in "Artist - Title" format.
    """

    def _fetch_orb_html(u: str) -> Optional[str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome Safari"
            )
        }
        try:
            resp = requests.get(u, headers=headers, timeout=20)
            resp.raise_for_status()
            text = resp.text
        except Exception:
            text = None
        if (not text) or (len(text) < 2000 and "/playlist" in u):
            try:
                parsed = urlparse(u)
                parts = [p for p in parsed.path.split("/") if p]
                if len(parts) >= 3 and parts[-1] == "playlist":
                    country = parts[-3]
                    station = parts[-2]
                    cs = f"{country}.{station}"
                    qs = dict(parse_qsl(parsed.query))
                    if "cs" not in qs:
                        qs["cs"] = cs
                        alt = parsed._replace(query=urlencode(qs))
                        r2 = requests.get(urlunparse(alt), headers=headers, timeout=20)
                        r2.raise_for_status()
                        text = r2.text
            except Exception:
                pass
        return text

    text = _fetch_orb_html(url)
    if not text:
        return []
    soup = BeautifulSoup(text, "lxml")
    cands: List[str] = []
    for row in soup.select(
        (
            ".playlist__item, .playlist tr, table[class*='playlist'] tr, "
            "table[id*='playlist'] tr, ul[class*='playlist'] li"
        )
    ):
        a_el = row.select_one(
            (
                ".playlist__artist, .artist, [itemprop='byArtist'], "
                ".song-artist, .playlist-artist"
            )
        )
        t_el = row.select_one(
            (
                ".playlist__title, .title, [itemprop='name'], .song-title, "
                ".playlist-title"
            )
        )
        if a_el and t_el:
            a = " ".join(a_el.stripped_strings)
            t = " ".join(t_el.stripped_strings)
            if a and t:
                cands.append(f"{a} - {t}")
                continue
        txt = " ".join(row.stripped_strings)
        if txt:
            cands.append(txt)
    if not cands:
        for el in soup.find_all(["li", "div", "span", "a", "p"]):
            txt = " ".join(el.stripped_strings)
            if txt:
                cands.append(txt)
    sep = re.compile(r"\s+[-—–]\s+")
    norm: List[str] = []
    for c in cands:
        c = " ".join(c.split())
        c = re.sub(r"^\d{1,2}:\d{2}\s+", "", c)
        if not sep.search(c):
            continue
        artist, title = re.split(sep, c, maxsplit=1)
        artist = artist.strip()
        title = re.split(r"\s{2,}|\s\|\s|\s•\s", title.strip())[0]
        if artist and title:
            norm.append(f"{artist} - {title}")
    norm = dedupe_preserve_order(norm)
    if max_tracks is not None:
        norm = norm[:max_tracks]
    return norm


def _extract_from_jsonld(soup: BeautifulSoup) -> List[str]:
    queries: List[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not isinstance(script, Tag):
            continue
        raw_any = script.string if script.string is not None else script.text
        if raw_any is None:
            raw_any = ""
        data = str(raw_any).strip()
        if not data:
            continue
        try:
            obj = json.loads(data)
        except Exception:
            continue
        for node in _json_nodes(obj):
            if not isinstance(node, dict):
                continue
            a = node.get("byArtist") or {}
            artist = a.get("name") if isinstance(a, dict) else None
            title = node.get("name")
            if isinstance(artist, str) and isinstance(title, str):
                artist = artist.strip()
                title = title.strip()
                if artist and title:
                    queries.append(f"{artist} - {title}")
    return dedupe_preserve_order(queries)


def _extract_from_dom_labels(soup: BeautifulSoup) -> List[str]:
    queries: List[str] = []
    containers = soup.select(
        "[class*='playlist'], [class*='Track'], [class*='track'], "
        "[data-component*='track'], [data-testid*='track']"
    )
    for c in containers or []:
        # Check container's own text
        c_text = " ".join(c.stripped_strings)
        if c_text and re.search(r"\s+[-—–]\s+", c_text):
            a, t = re.split(r"\s+[-—–]\s+", c_text, maxsplit=1)
            a = a.strip()
            t = t.strip()
            if a and t:
                queries.append(f"{a} - {t}")
        # Check children
        for it in c.find_all(True, recursive=True):
            text = " ".join(it.stripped_strings)
            if not text:
                continue
            if re.search(r"\s+[-—–]\s+", text):
                artist, title = re.split(r"\s+[-—–]\s+", text, maxsplit=1)
                artist = artist.strip()
                title = title.strip()
                if artist and title:
                    queries.append(f"{artist} - {title}")
    return dedupe_preserve_order(queries)


def _extract_from_any_json_scripts(soup: BeautifulSoup) -> List[str]:
    queries: List[str] = []
    for script in soup.find_all("script"):
        if not isinstance(script, Tag):
            continue
        raw_any = script.string if script.string is not None else script.text
        if raw_any is None:
            raw_any = ""
        text = str(raw_any).strip()
        if not text:
            continue
        if not (text.startswith("{") or text.startswith("[")):
            m = re.search(r"(\{.*\})", text, re.DOTALL)
            if not m:
                continue
            text = m.group(1)
        try:
            obj = json.loads(text)
        except Exception:
            continue
        for node in _json_nodes(obj):
            if not isinstance(node, dict):
                continue
            a = node.get("artist") or node.get("artistName")
            if isinstance(a, dict):
                a = a.get("name")
            t = node.get("title") or node.get("trackTitle")
            if isinstance(a, str) and isinstance(t, str) and a.strip() and t.strip():
                queries.append(f"{a.strip()} - {t.strip()}")
    return dedupe_preserve_order(queries)


def _extract_from_regex(text: str) -> List[str]:
    queries: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^\d{1,2}:\d{2}\s+", "", line)
        m = re.search(r"^(.{1,80})\s+[-—–]\s+(.{1,120})$", line)
        if m:
            a = m.group(1).strip()
            t = m.group(2).strip()
            queries.append(f"{a} - {t}")
    return dedupe_preserve_order(queries)


def get_track_queries_from_dr_urls(
    urls: List[str],
    max_tracks: Optional[int] = None,
    debug: bool = False,
    keep_duplicates: bool = False,
) -> List[str]:
    """Scrape DR program playlist pages and aggregate queries.

    Args:
        urls: DR program playlist page URLs.
        max_tracks: Optional limit over the aggregate list.
        debug: If True, prints extraction counts to stderr.
        keep_duplicates: If True, do not dedupe within aggregate.

    Returns:
        Queries in "Artist - Title" format.
    """
    all_queries: List[str] = []
    for url in urls:
        html = _fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        q = _extract_from_next_data_playlist_points(
            soup, debug=debug, dedupe=not keep_duplicates
        )
        if debug:
            print(
                f"DEBUG: {url} -> NEXT_DATA playlistIndexPoints: {len(q)}",
                flush=True,
            )
        if not q:
            q = _extract_from_jsonld(soup)
            if debug:
                print(f"DEBUG: {url} -> JSON-LD matches: {len(q)}", flush=True)
        if not q:
            q = _extract_from_dom_labels(soup)
            if debug:
                print(
                    f"DEBUG: {url} -> DOM label matches: {len(q)}",
                    flush=True,
                )
        if not q:
            q = _extract_from_any_json_scripts(soup)
            if debug:
                print(
                    f"DEBUG: {url} -> Any-JSON matches: {len(q)}",
                    flush=True,
                )
        if not q:
            q = _extract_from_regex(soup.get_text("\n"))
            if debug:
                print(f"DEBUG: {url} -> Regex matches: {len(q)}", flush=True)
        if q:
            all_queries.extend(q)
    if not keep_duplicates:
        all_queries = dedupe_preserve_order(all_queries)
    if max_tracks is not None:
        all_queries = all_queries[:max_tracks]
    return all_queries


def discover_dr_program_urls(station: str, date: str, debug: bool = False) -> List[str]:
    """Discover DR program playlist URLs for a station/date.

    Args:
        station: Station key, e.g., "p3".
        date: Date string YYYY-MM-DD.
        debug: Print discovery count if True.

    Returns:
        List of discovered absolute URLs.
    """
    base = f"https://www.dr.dk/lyd/playlister/{station}/{date}"
    html = _fetch_html(base) or _fetch_html(base + "/")
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    found: List[str] = []
    base_path = f"/lyd/playlister/{station}/{date}/"
    for el in soup.find_all("a", href=True):
        # Pylance: ensure we operate on Tag, not NavigableString/PageElement
        if not isinstance(el, Tag):
            continue
        href_val = el.get("href")
        if not isinstance(href_val, str):
            continue
        if base_path in href_val:
            url_str: str = href_val
            if not url_str.startswith("http"):
                url_str = urljoin("https://www.dr.dk", url_str)
            url_str = url_str.split("#")[0]
            found.append(url_str)
    if not found:
        pat_abs = (
            rf"https?://www\.dr\.dk/lyd/playlister/{re.escape(station)}/"
            rf"{re.escape(date)}/[\w\-\d]+"
        )
        for m in re.finditer(pat_abs, html):
            found.append(m.group(0))
        pat_rel = (
            rf"(/lyd/playlister/{re.escape(station)}/{re.escape(date)}/" rf"[\w\-\d]+)"
        )
        for m in re.finditer(pat_rel, html):
            found.append(urljoin("https://www.dr.dk", m.group(1)))
    found = dedupe_preserve_order(found)
    if debug:
        print(
            f"DEBUG: Discovered {len(found)} DR program URLs for {station} {date}",
            flush=True,
        )
    return found
