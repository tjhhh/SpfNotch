import ctypes
from ctypes import wintypes
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
