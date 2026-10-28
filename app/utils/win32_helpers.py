import ctypes
from ctypes import wintypes
import sys

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000

user32 = ctypes.windll.user32 if sys.platform == "win32" else None

def set_no_activate(hwnd: int, enable: bool = True):
    """
    Sets or removes WS_EX_NOACTIVATE on a window HWND.
    When enabled, mouse clicks on the window will not steal focus from
    the user's currently active application (e.g., Code editor or browser).
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
        user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"[win32_helpers] Failed to activate window focus: {e}")

def set_tool_window(hwnd: int):
    """
    Hides the window from the Windows taskbar and Alt+Tab menu.
    """
    if not user32 or not hwnd:
        return
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception as e:
        print(f"[win32_helpers] Failed to set tool window: {e}")
