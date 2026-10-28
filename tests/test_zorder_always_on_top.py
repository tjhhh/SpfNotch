import sys
import os
import ctypes
from ctypes import wintypes

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit
from PyQt6.QtCore import Qt
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow
from app.utils.win32_helpers import (
    ensure_topmost,
    set_no_activate,
    set_tool_window,
    WS_EX_TOPMOST,
    WS_EX_TOOLWINDOW,
    WS_EX_NOACTIVATE,
    GWL_EXSTYLE,
    user32,
)

def test_notch_zorder_and_topmost():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)

    notch_win = NotchWindow(state_manager, image_cache, {})
    notch_win.show()
    notch_hwnd = int(notch_win.winId())

    assert notch_hwnd != 0, "NotchWindow HWND must be valid"

    # 1. Verify Extended Styles on Windows
    if sys.platform == "win32" and user32:
        style = user32.GetWindowLongW(notch_hwnd, GWL_EXSTYLE)
        assert bool(style & WS_EX_TOPMOST), "NotchWindow must have WS_EX_TOPMOST flag"
        assert bool(style & WS_EX_TOOLWINDOW), "NotchWindow must have WS_EX_TOOLWINDOW flag"
        assert bool(style & WS_EX_NOACTIVATE), "NotchWindow must have WS_EX_NOACTIVATE flag"
        print("[PASS] Extended style flags verified (TOPMOST, TOOLWINDOW, NOACTIVATE)")

    # 2. Verify Z-Order Enforcer against another Topmost Window
    if sys.platform == "win32" and user32:
        # Create a competitor topmost window that gets shown after NotchWindow
        w2 = QWidget()
        w2.setWindowTitle("CompetitorTopmost")
        w2.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        w2.show()
        w2_hwnd = int(w2.winId())

        # Ensure Notch window is elevated to absolute top of Z-order
        ensure_topmost(notch_hwnd)

        order = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(h, lp):
            if h in (notch_hwnd, w2_hwnd):
                order.append(h)
            return True
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        assert len(order) == 2, f"Both windows must be enumerated, got {order}"
        assert order[0] == notch_hwnd, f"NotchWindow must be at the top of Z-order ahead of competitor, got {order}"
        print("[PASS] ensure_topmost elevates NotchWindow above competitor topmost window")

        w2.close()

    # 3. Verify Zero Focus-Stealing
    if sys.platform == "win32" and user32:
        # Create an external focused window
        focused_app = QWidget()
        focused_app.setWindowTitle("FocusedEditor")
        line_edit = QLineEdit(focused_app)
        focused_app.show()
        focused_app.activateWindow()
        line_edit.setFocus()

        user32.SetForegroundWindow(int(focused_app.winId()))
        fg_before = user32.GetForegroundWindow()

        # Call ensure_topmost and _maintain_topmost_zorder
        ensure_topmost(notch_hwnd)
        notch_win._maintain_topmost_zorder()

        fg_after = user32.GetForegroundWindow()
        assert fg_before == fg_after, f"ensure_topmost must NOT steal focus! Before: {fg_before}, After: {fg_after}"
        print("[PASS] Zero focus-stealing verified")

        focused_app.close()

    # 4. Verify Z-order Watchdog timer exists and is active
    assert hasattr(notch_win, "zorder_watchdog"), "NotchWindow must have zorder_watchdog attribute"
    assert notch_win.zorder_watchdog.isActive(), "zorder_watchdog timer must be active"
    assert notch_win.zorder_watchdog.interval() == 1000, "zorder_watchdog interval should be 1000ms"
    print("[PASS] Persistent Z-order watchdog timer verified")

    # 5. Verify Expand and Collapse maintain topmost without crashing
    notch_win.expand()
    assert notch_win.is_expanded == True
    notch_win.collapse()
    assert notch_win.is_expanded == False
    print("[PASS] Expand & Collapse with topmost reinforcement verified")

    notch_win.close()
    print("All Always-On-Top Z-Order tests passed successfully!")

if __name__ == "__main__":
    test_notch_zorder_and_topmost()
