import os
import re
import json
import bisect
import hashlib
import urllib.parse
import requests

class LyricsClient:
    def __init__(self):
        self._cache = {}
        self._lrc_regex = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.disk_cache_dir = os.path.join(base_dir, ".cache", "lyrics")

    def _get_disk_cache(self, cache_key: str) -> dict | None:
        try:
            h = hashlib.sha256(cache_key.encode('utf-8')).hexdigest()
            p = os.path.join(self.disk_cache_dir, f"{h}.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_disk_cache(self, cache_key: str, data: dict):
        try:
            os.makedirs(self.disk_cache_dir, exist_ok=True)
            h = hashlib.sha256(cache_key.encode('utf-8')).hexdigest()
            p = os.path.join(self.disk_cache_dir, f"{h}.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[LyricsClient] Error saving disk cache: {e}")

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercases and strips non-alphanumeric chars for strict title/artist verification."""
        return re.sub(r'[^a-z0-9\s]', ' ', (text or '').lower()).strip()

    def _is_matching_result(self, item: dict, clean_title: str, artist_name: str, duration_sec: int) -> bool:
        """
        Ensures an LRCLIB search result genuinely belongs to the requested track.
        Allows up to 55s duration tolerance to accommodate video klip / radio edit variations.
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

        # Generous duration tolerance (up to 55s difference) for music video / extended versions
        item_dur = item.get("duration")
        if duration_sec > 0 and item_dur:
            try:
                if abs(float(item_dur) - float(duration_sec)) > 55:
                    return False
            except Exception:
                pass

        return True

    def fetch_lyrics(self, track_name: str, artist_name: str, album_name: str = "", duration_sec: int = 0) -> dict | None:
        """
        Fetches synced lyrics using multi-stage LRCLIB queries and fallback providers.
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

        disk_cached = self._get_disk_cache(cache_key)
        if disk_cached and disk_cached.get("lines"):
            self._cache[cache_key] = disk_cached
            return disk_cached

        primary_artist = artist_name.split(",")[0].strip()
        headers = {'User-Agent': 'spfnotch/1.0 (Spotify Dynamic Notch for Windows)'}

        # -------------------------------------------------------------
        # STAGE 1: Exact query via /api/get (first with duration, then without)
        # -------------------------------------------------------------
        for cand_artist in dict.fromkeys([artist_name, primary_artist]):
            if not cand_artist:
                continue

            # 1a. Try with exact duration
            if duration_sec > 0:
                try:
                    params = {"track_name": clean_title, "artist_name": cand_artist, "duration": str(duration_sec)}
                    resp = requests.get(f"https://lrclib.net/api/get?{urllib.parse.urlencode(params)}", headers=headers, timeout=6)
                    if resp.status_code == 200:
                        data = resp.json()
                        if self._is_matching_result(data, clean_title, artist_name, duration_sec):
                            parsed = self._parse_lrclib_response(data, duration_sec)
                            if parsed.get("lines"):
                                self._cache[cache_key] = parsed
                                self._save_disk_cache(cache_key, parsed)
                                return parsed
                except Exception:
                    pass

            # 1b. Try without duration parameter
            try:
                params = {"track_name": clean_title, "artist_name": cand_artist}
                resp = requests.get(f"https://lrclib.net/api/get?{urllib.parse.urlencode(params)}", headers=headers, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    if self._is_matching_result(data, clean_title, artist_name, duration_sec):
                        parsed = self._parse_lrclib_response(data, duration_sec)
                        if parsed.get("lines"):
                            self._cache[cache_key] = parsed
                            self._save_disk_cache(cache_key, parsed)
                            return parsed
            except Exception:
                pass

        # -------------------------------------------------------------
        # STAGE 2: Validated search query on LRCLIB (/api/search)
        # -------------------------------------------------------------
        for query_artist in dict.fromkeys([primary_artist, artist_name]):
            fallback = self._search_lrclib(clean_title, query_artist, artist_name, duration_sec)
            if fallback and fallback.get("lines"):
                self._cache[cache_key] = fallback
                self._save_disk_cache(cache_key, fallback)
                return fallback

        # -------------------------------------------------------------
        # STAGE 3: Secondary Providers Fallback (Lyrics.ovh & NetEase)
        # -------------------------------------------------------------
        secondary = self._fetch_from_lyrics_ovh(clean_title, primary_artist, duration_sec)
        if secondary and secondary.get("lines"):
            self._cache[cache_key] = secondary
            self._save_disk_cache(cache_key, secondary)
            return secondary

        netease = self._fetch_from_netease(clean_title, primary_artist, duration_sec)
        if netease and netease.get("lines"):
            self._cache[cache_key] = netease
            self._save_disk_cache(cache_key, netease)
            return netease

        empty_res = {"synced": False, "lines": [], "timestamps": [], "raw": ""}
        self._cache[cache_key] = empty_res
        return empty_res

    def _search_lrclib(self, clean_title: str, query_artist: str, full_artist: str, duration_sec: int) -> dict | None:
        """Searches LRCLIB via /api/search using structured and free-text queries."""
        headers = {'User-Agent': 'spfnotch/1.0 (Spotify Dynamic Notch for Windows)'}
        queries = [
            f"https://lrclib.net/api/search?{urllib.parse.urlencode({'track_name': clean_title, 'artist_name': query_artist})}",
            f"https://lrclib.net/api/search?{urllib.parse.urlencode({'q': f'{clean_title} {query_artist}'})}"
        ]

        for url in queries:
            try:
                resp = requests.get(url, headers=headers, timeout=6)
                if resp.status_code == 200:
                    results = resp.json()
                    if results and isinstance(results, list):
                        # 1. Prefer synced lyrics that match title & artist
                        for item in results:
                            if item.get("syncedLyrics") and self._is_matching_result(item, clean_title, full_artist, duration_sec):
                                return self._parse_lrclib_response(item, duration_sec)
                        # 2. Plain lyrics with pacing fallback
                        for item in results:
                            if item.get("plainLyrics") and self._is_matching_result(item, clean_title, full_artist, duration_sec):
                                return self._parse_lrclib_response(item, duration_sec)
            except Exception as e:
                print(f"[LyricsClient] search_lrclib error: {e}")
        return None

    def _fetch_from_lyrics_ovh(self, clean_title: str, query_artist: str, duration_sec: int) -> dict | None:
        try:
            url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(query_artist)}/{urllib.parse.quote(clean_title)}"
            headers = {'User-Agent': 'spfnotch/1.0'}
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                lyrics = data.get("lyrics", "").strip()
                if lyrics:
                    return self._parse_plain_lyrics(lyrics, duration_sec)
        except Exception as e:
            print(f"[LyricsClient] lyrics.ovh error: {e}")
        return None

    def _fetch_from_netease(self, clean_title: str, query_artist: str, duration_sec: int) -> dict | None:
        try:
            search_url = f"https://music.xianqiao.wang/neteaseapiv2/search?keywords={urllib.parse.quote(clean_title + ' ' + query_artist)}&type=1&limit=3"
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(search_url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                songs = data.get("data", {}).get("songs", []) or data.get("result", {}).get("songs", [])
                if songs:
                    song_id = songs[0].get("id")
                    if song_id:
                        lyric_url = f"https://music.163.com/api/song/lyric?os=pc&id={song_id}&lv=-1&kv=-1&tv=-1"
                        l_resp = requests.get(lyric_url, headers=headers, timeout=6)
                        if l_resp.status_code == 200:
                            l_data = l_resp.json()
                            lrc_str = l_data.get("lrc", {}).get("lyric", "")
                            if lrc_str:
                                lines = self._parse_lrc(lrc_str)
                                if lines:
                                    return {
                                        "synced": True,
                                        "lines": lines,
                                        "timestamps": [l["time_ms"] for l in lines],
                                        "raw": lrc_str
                                    }
        except Exception as e:
            print(f"[LyricsClient] NetEase fallback error: {e}")
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
            return self._parse_plain_lyrics(plain_text, duration_sec)

        return {"synced": False, "lines": [], "timestamps": [], "raw": ""}

    def _parse_plain_lyrics(self, plain_text: str, duration_sec: int) -> dict:
        lines_text = [l.strip() for l in plain_text.splitlines() if l.strip()]
        if not lines_text:
            return {"synced": False, "lines": [], "timestamps": [], "raw": ""}

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
