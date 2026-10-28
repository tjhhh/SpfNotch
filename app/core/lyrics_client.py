import re
import urllib.parse
import urllib.request
import json
import bisect

class LyricsClient:
    def __init__(self):
        self._cache = {}
        self._lrc_regex = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercases and strips non-alphanumeric chars for strict title/artist verification."""
        return re.sub(r'[^a-z0-9\s]', ' ', (text or '').lower()).strip()

    def _is_matching_result(self, item: dict, clean_title: str, artist_name: str, duration_sec: int) -> bool:
        """
        Ensures an LRCLIB search result genuinely belongs to the requested track
        (prevents false-positive matches like Japanese songs matching '86' in artist name).
        """
        item_title = self._normalize(item.get("trackName") or item.get("name") or "")
        target_title = self._normalize(clean_title)
        if not item_title or not target_title:
            return False

        # Title must match closely
        title_matches = (target_title in item_title) or (item_title in target_title)
        if not title_matches:
            return False

        # At least one artist name segment must match the result's artistName
        item_artist = self._normalize(item.get("artistName") or "")
        raw_artists = [a.strip() for a in re.split(r',|&|\bfeat\.?\b|\bft\.?\b', artist_name) if a.strip()]
        artist_matches = False
        for art in raw_artists:
            norm_art = self._normalize(art)
            if norm_art and (norm_art in item_artist or item_artist in norm_art):
                artist_matches = True
                break

        if not artist_matches:
            return False

        # If both have duration, ensure they are within 20 seconds of each other
        item_dur = item.get("duration")
        if duration_sec > 0 and item_dur:
            try:
                if abs(float(item_dur) - float(duration_sec)) > 20:
                    return False
            except Exception:
                pass

        return True

    def fetch_lyrics(self, track_name: str, artist_name: str, album_name: str = "", duration_sec: int = 0) -> dict | None:
        """
        Fetches synced lyrics from LRCLIB with strict title & artist validation.
        If no matching lyrics exist, returns empty lines so UI displays Title & Author only.
        """
        if not track_name or not artist_name:
            return {"synced": False, "lines": [], "timestamps": [], "raw": ""}

        # Clean title (e.g. remove " - Remastered 2021", "(feat. XYZ)") for optimal matching
        clean_title = re.sub(r'\(.*?\)|\[.*?\]|- .*', '', track_name).strip()
        if not clean_title:
            clean_title = track_name.strip()

        cache_key = f"{artist_name.lower()}::{clean_title.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        primary_artist = artist_name.split(",")[0].strip()

        # 1. Exact query via /api/get (try full artist, then primary artist)
        for cand_artist in dict.fromkeys([artist_name, primary_artist]):
            if not cand_artist:
                continue
            params = {
                "track_name": clean_title,
                "artist_name": cand_artist,
            }
            if duration_sec > 0:
                params["duration"] = str(duration_sec)

            url = f"https://lrclib.net/api/get?{urllib.parse.urlencode(params)}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'spfnotch/1.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode('utf-8'))
                        if self._is_matching_result(data, clean_title, artist_name, duration_sec):
                            parsed = self._parse_lrclib_response(data, duration_sec)
                            if parsed.get("lines"):
                                self._cache[cache_key] = parsed
                                return parsed
            except Exception:
                pass

        # 2. Validated fallback search query (try primary artist first, then full artist)
        for query_artist in dict.fromkeys([primary_artist, artist_name]):
            fallback = self._search_fallback(clean_title, query_artist, artist_name, duration_sec)
            if fallback and fallback.get("lines"):
                self._cache[cache_key] = fallback
                return fallback

        empty_res = {"synced": False, "lines": [], "timestamps": [], "raw": ""}
        self._cache[cache_key] = empty_res
        return empty_res

    def _search_fallback(self, clean_title: str, query_artist: str, full_artist: str, duration_sec: int) -> dict | None:
        """Searches LRCLIB via /api/search and strictly validates title + artist match."""
        try:
            q = urllib.parse.urlencode({"q": f"{clean_title} {query_artist}"})
            url = f"https://lrclib.net/api/search?{q}"
            req = urllib.request.Request(url, headers={'User-Agent': 'spfnotch/1.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    results = json.loads(resp.read().decode('utf-8'))
                    if results and isinstance(results, list):
                        # Prefer synced lyrics that strictly match title & artist
                        for item in results:
                            if item.get("syncedLyrics") and self._is_matching_result(item, clean_title, full_artist, duration_sec):
                                return self._parse_lrclib_response(item, duration_sec)
                        # Otherwise allow plain lyrics that strictly match title & artist
                        for item in results:
                            if item.get("plainLyrics") and self._is_matching_result(item, clean_title, full_artist, duration_sec):
                                return self._parse_lrclib_response(item, duration_sec)
        except Exception as e:
            print(f"[LyricsClient] search_fallback error: {e}")
        return None

    def _parse_lrclib_response(self, data: dict, duration_sec: int) -> dict:
        synced_lrc = data.get("syncedLyrics")
        plain_text = data.get("plainLyrics")

        if synced_lrc:
            lines = self._parse_lrc(synced_lrc)
            if lines:
                return {
                    "synced": True,
                    "lines": lines,
                    "timestamps": [line["time_ms"] for line in lines],
                    "raw": synced_lrc
                }

        if plain_text:
            lines_text = [l.strip() for l in plain_text.splitlines() if l.strip()]
            if lines_text:
                total_ms = duration_sec * 1000 if duration_sec > 0 else 180000
                intro_ms = min(15000, int(total_ms * 0.1))
                available_ms = max(5000, total_ms - intro_ms - 10000)
                step_ms = available_ms / max(1, len(lines_text))

                lines = []
                timestamps = []
                for i, text in enumerate(lines_text):
                    t_ms = int(intro_ms + i * step_ms)
                    lines.append({"time_ms": t_ms, "text": text})
                    timestamps.append(t_ms)

                return {
                    "synced": True,
                    "lines": lines,
                    "timestamps": timestamps,
                    "raw": plain_text
                }

        return {"synced": False, "lines": [], "timestamps": [], "raw": ""}

    def _parse_lrc(self, lrc_text: str) -> list[dict]:
        lines = []
        for raw_line in lrc_text.splitlines():
            raw_line = raw_line.strip()
            match = self._lrc_regex.match(raw_line)
            if match:
                mins = int(match.group(1))
                secs = int(match.group(2))
                ms_str = match.group(3)
                if len(ms_str) == 2:
                    ms = int(ms_str) * 10
                else:
                    ms = int(ms_str[:3])
                total_ms = (mins * 60 + secs) * 1000 + ms
                text = match.group(4).strip()
                if text:
                    lines.append({"time_ms": total_ms, "text": text})

        lines.sort(key=lambda x: x["time_ms"])
        return lines

    @staticmethod
    def find_active_index(timestamps: list[int], current_ms: int) -> int:
        if not timestamps:
            return -1
        idx = bisect.bisect_right(timestamps, current_ms) - 1
        return max(0, idx) if idx >= 0 else 0
