import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_TOP = 0

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SWP_NOOWNERZORDER = 0x0200

TOPMOST_FLAGS = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_NOOWNERZORDER

user32 = ctypes.windll.user32 if sys.platform == "win32" else None
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

WM_APPCOMMAND = 0x0319
APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
APPCOMMAND_MEDIA_STOP = 13
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
APPCOMMAND_MEDIA_PLAY = 46
APPCOMMAND_MEDIA_PAUSE = 47
SMTO_ABORTIFHUNG = 0x0002

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_RETURN = 0x0D
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

def ensure_topmost(hwnd: int):
    """
    Forces the window HWND to the absolute top of the Z-order (above all other
    topmost windows, normal windows, and desktop widgets) without stealing user focus.
    """
    if not user32 or not hwnd:
        return
    try:
        # 1. Ensure WS_EX_TOPMOST attribute is active and above all standard windows
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            TOPMOST_FLAGS
        )
        # 2. Place window at the absolute top of the topmost Z-band
        user32.SetWindowPos(
            hwnd,
            HWND_TOP,
            0, 0, 0, 0,
            TOPMOST_FLAGS
        )
    except Exception as e:
        print(f"[win32_helpers] Failed to ensure topmost: {e}")

def set_no_activate(hwnd: int, enable: bool = True):
    """
    Sets or removes WS_EX_NOACTIVATE on a window HWND.
    When enabled, mouse clicks on the window will not steal focus from
    the user's currently active application (e.g., Code editor or browser).
    Also refreshes the frame styles and reasserts topmost status.
    """
    if not user32 or not hwnd:
        return
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            style |= WS_EX_NOACTIVATE
        else:
            style &= ~WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            TOPMOST_FLAGS | SWP_FRAMECHANGED
        )
    except Exception as e:
        print(f"[win32_helpers] Failed to set no_activate: {e}")

def activate_window_focus(hwnd: int):
    """
    Temporarily brings the window to the foreground and removes WS_EX_NOACTIVATE
    so the user can type or paste text into input fields.
    """
    if not user32 or not hwnd:
        return
    try:
        set_no_activate(hwnd, enable=False)
        ensure_topmost(hwnd)
        user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"[win32_helpers] Failed to activate window focus: {e}")

def set_tool_window(hwnd: int):
    """
    Hides the window from the Windows taskbar and Alt+Tab menu,
    and applies frame changes while keeping topmost priority.
    """
    if not user32 or not hwnd:
        return
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            TOPMOST_FLAGS | SWP_FRAMECHANGED
        )
    except Exception as e:
        print(f"[win32_helpers] Failed to set tool window: {e}")


def _is_spotify_process(hwnd: int) -> bool:
    """Checks if a window HWND belongs to Spotify.exe."""
    if not user32 or not kernel32 or not hwnd:
        return False
    try:
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
        hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hproc:
            return False
        try:
            buf_len = wintypes.DWORD(512)
            buf = ctypes.create_unicode_buffer(512)
            if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(buf_len)):
                exe_path = buf.value.lower()
                return exe_path.endswith("\\spotify.exe") or exe_path.endswith("/spotify.exe")
        finally:
            kernel32.CloseHandle(hproc)
    except Exception:
        pass
    return False


def find_spotify_hwnd() -> tuple[int | None, str]:
    """
    Finds the main top-level window HWND of Spotify.exe and returns (hwnd, window_title).
    """
    if not user32:
        return None, ""
    matches: list[tuple[int, str, bool]] = []

    def _enum_cb(hwnd, _):
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            cls_buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls_buf, 128)
            if not cls_buf.value.startswith("Chrome_WidgetWin_"):
                return True
            if not _is_spotify_process(hwnd):
                return True
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
            title = title_buf.value.strip()
            if title and title not in ("Default IME", "MSCTFIME UI"):
                is_vis = bool(user32.IsWindowVisible(hwnd))
                matches.append((hwnd, title, is_vis))
        except Exception:
            pass
        return True

    try:
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
    except Exception:
        return None, ""

    if not matches:
        return None, ""

    # Prefer visible window or window actively displaying 'Artist - Title'
    for hwnd, title, is_vis in matches:
        if is_vis and " - " in title:
            return hwnd, title
    for hwnd, title, is_vis in matches:
        if is_vis:
            return hwnd, title
    return matches[0][0], matches[0][1]


def get_windows_media_session() -> dict | None:
    """
    Queries Windows GSMTC (Global System Media Transport Controls) via PowerShell.
    Returns:
      {
        "app_id": str,
        "is_playing": bool,
        "title": str,
        "artist": str,
        "album": str,
        "progress_ms": int,
        "duration_ms": int,
      } or None if no media session / error.
    """
    if sys.platform != "win32":
        return None
    try:
        script_path = os.path.join(os.path.dirname(__file__), "get_media_session.ps1")
        if not os.path.exists(script_path):
            return None
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Action", "status"],
            capture_output=True,
            text=True,
            timeout=2.0,
            creationflags=creationflags,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        data = json.loads(proc.stdout.strip())
        title = (data.get("Title") or "").strip()
        artist = (data.get("Artist") or "").strip()
        album = (data.get("Album") or "").strip()
        status = data.get("Status") or "Paused"
        is_playing = (status == "Playing")
        app_id = (data.get("AppId") or "").strip()
        pos_ms = int(data.get("PositionMs", 0) or 0)
        dur_ms = int(data.get("DurationMs", 0) or 0)

        if not title:
            return None

        return {
            "app_id": app_id,
            "is_playing": is_playing,
            "title": title,
            "artist": artist,
            "album": album,
            "progress_ms": pos_ms,
            "duration_ms": dur_ms,
        }
    except Exception as e:
        return None


def send_windows_media_action(action: str) -> bool:
    """
    Sends a transport control action ('play', 'pause', 'toggle', 'next', 'prev')
    directly to the active Windows GSMTC session via PowerShell helper.
    """
    if sys.platform != "win32":
        return False
    try:
        script_path = os.path.join(os.path.dirname(__file__), "get_media_session.ps1")
        if not os.path.exists(script_path):
            return False
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Action", action],
            capture_output=True,
            text=True,
            timeout=2.5,
            creationflags=creationflags,
        )
        return proc.returncode == 0
    except Exception as e:
        print(f"[win32_helpers] send_windows_media_action error: {e}")
        return False


def get_spotify_window_track() -> dict | None:
    """
    Reads local Spotify Desktop playback on Windows using GSMTC with window title fallback.
    Returns:
      - None if Spotify Desktop is not running
      - {'is_playing': False, 'title': title, 'artist': artist, 'album': album, 'progress_ms': pos, 'duration_ms': dur, 'hwnd': hwnd} when paused
      - {'is_playing': True, 'title': title, 'artist': artist, 'album': album, 'progress_ms': pos, 'duration_ms': dur, 'raw_title': raw, 'hwnd': hwnd} when playing
    """
    hwnd, raw_title = find_spotify_hwnd()

    # 1. Primary: Query Windows GSMTC for rich status, title, artist, album, and exact timeline position
    media = get_windows_media_session()
    if media and media.get("title"):
        return {
            "is_playing": media.get("is_playing", False),
            "artist": media.get("artist", ""),
            "title": media.get("title", ""),
            "album": media.get("album", ""),
            "progress_ms": media.get("progress_ms", 0),
            "duration_ms": media.get("duration_ms", 0),
            "raw_title": f"{media.get('artist')} - {media.get('title')}",
            "hwnd": hwnd,
        }

    # 2. Fallback to Window Title inspection if GSMTC not available
    idle_titles = {"spotify", "spotify free", "spotify premium"}
    if hwnd and raw_title and " - " in raw_title and raw_title.lower() not in idle_titles:
        artist, title = raw_title.split(" - ", 1)
        return {
            "is_playing": True,
            "artist": artist.strip(),
            "title": title.strip(),
            "album": "",
            "progress_ms": 0,
            "duration_ms": 0,
            "raw_title": raw_title,
            "hwnd": hwnd,
        }

    if not hwnd or not raw_title:
        return None

    if raw_title.lower() in idle_titles:
        return {
            "is_playing": False,
            "title": "",
            "artist": "",
            "album": "",
            "progress_ms": 0,
            "duration_ms": 0,
            "raw_title": raw_title,
            "hwnd": hwnd,
        }

    return {
        "is_playing": True,
        "artist": "Spotify",
        "title": raw_title.strip(),
        "album": "",
        "progress_ms": 0,
        "duration_ms": 0,
        "raw_title": raw_title,
        "hwnd": hwnd,
    }


def send_spotify_media_command(command: str) -> bool:
    """
    Sends a local media transport command ('play_pause', 'play', 'pause', 'next', 'prev')
    directly to Spotify Desktop on Windows without using the Spotify Web API.
    Uses Windows GSMTC as primary, falling back to WM_APPCOMMAND and virtual media keys.
    """
    # 1. Primary: Try Windows GSMTC transport control directly
    action_map = {
        "play_pause": "toggle",
        "play": "play",
        "pause": "pause",
        "next": "next",
        "prev": "prev",
    }
    gsmtc_act = action_map.get(command)
    if gsmtc_act:
        if send_windows_media_action(gsmtc_act):
            return True

    if not user32:
        return False

    cmd_map = {
        "play_pause": APPCOMMAND_MEDIA_PLAY_PAUSE,
        "play": APPCOMMAND_MEDIA_PLAY,
        "pause": APPCOMMAND_MEDIA_PAUSE,
        "next": APPCOMMAND_MEDIA_NEXTTRACK,
        "prev": APPCOMMAND_MEDIA_PREVIOUSTRACK,
        "stop": APPCOMMAND_MEDIA_STOP,
    }
    vk_map = {
        "play_pause": VK_MEDIA_PLAY_PAUSE,
        "play": VK_MEDIA_PLAY_PAUSE,
        "pause": VK_MEDIA_PLAY_PAUSE,
        "next": VK_MEDIA_NEXT_TRACK,
        "prev": VK_MEDIA_PREV_TRACK,
        "stop": VK_MEDIA_STOP,
    }

    # 2. Secondary: Send WM_APPCOMMAND to Spotify HWND
    app_cmd = cmd_map.get(command, APPCOMMAND_MEDIA_PLAY_PAUSE)
    hwnd, _ = find_spotify_hwnd()
    if hwnd:
        try:
            res = wintypes.DWORD(0)
            lparam = app_cmd << 16
            ok = user32.SendMessageTimeoutW(
                hwnd, WM_APPCOMMAND, hwnd, lparam, SMTO_ABORTIFHUNG, 500, ctypes.byref(res)
            )
            if ok:
                return True
        except Exception as e:
            print(f"[win32_helpers] SendMessageTimeoutW failed: {e}")

    # 3. Tertiary: Fallback to global virtual media key
    vk = vk_map.get(command, VK_MEDIA_PLAY_PAUSE)
    try:
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return True
    except Exception as e:
        print(f"[win32_helpers] keybd_event failed: {e}")
        return False


def play_spotify_uri_locally(uri: str) -> bool:
    """
    Opens a Spotify URI (e.g. 'spotify:track:xxxx') directly in the local Spotify Desktop
    client on Windows via OS protocol handler and ensures playback starts via helper.
    """
    if sys.platform != "win32" or not uri or not uri.startswith("spotify:"):
        return False
    try:
        import os
        import time
        script_path = os.path.join(os.path.dirname(__file__), "get_media_session.ps1")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        # 1. Primary: Use PowerShell helper to navigate URI, activate Spotify, and press Enter
        if os.path.exists(script_path):
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Action", "play_uri", "-Uri", uri],
                capture_output=True,
                text=True,
                timeout=3.5,
                creationflags=creationflags,
            )
        else:
            os.startfile(uri)

        # 2. Wait up to 1.5s for playback to engage
        for _ in range(5):
            time.sleep(0.2)
            info = get_spotify_window_track()
            if info and info.get("is_playing"):
                return True

        # 3. If still not playing, force Play command via GSMTC
        send_windows_media_action("play")
        time.sleep(0.2)

        info = get_spotify_window_track()
        if info and info.get("is_playing"):
            return True

        # 4. Fallback: send toggle
        send_windows_media_action("toggle")
        return True
    except Exception as e:
        print(f"[win32_helpers] play_spotify_uri_locally error: {e}")
        return False
