import sys
import os
import json

# AppUserModelID for Windows Taskbar pinning and proper taskbar grouping
if sys.platform == "win32":
    try:
        import ctypes
        myappid = "spfnotch.desktop.app"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"[Main] Error setting AppUserModelID: {e}")

# Determine application and resource directories (works frozen as .exe and from source)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = getattr(sys, '_MEIPASS', APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RESOURCE_DIR = APP_DIR

if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow

LOCAL_SERVER_NAME = "spfnotch_SingleInstance_IPC"

def get_app_icon() -> QIcon | None:
    """Finds and returns the best available application icon."""
    for base in [RESOURCE_DIR, APP_DIR]:
        for sub in [os.path.join("app", "assets"), "assets"]:
            for name in ["icon.ico", "icon.png"]:
                candidate = os.path.join(base, sub, name)
                if os.path.exists(candidate):
                    return QIcon(candidate)
    return None

WIN32_MUTEX_HANDLE = None

def acquire_win32_mutex(mutex_name: str = "Global\\spfnotch_SingleInstance_Mutex") -> bool:
    """
    Acquires a named kernel mutex on Windows.
    Returns True if this is the first/only instance holding the mutex.
    Returns False if another instance is already running (GetLastError == 183 ERROR_ALREADY_EXISTS).
    """
    global WIN32_MUTEX_HANDLE
    if sys.platform != "win32":
        return True
    try:
        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            if handle:
                kernel32.CloseHandle(handle)
            return False
        WIN32_MUTEX_HANDLE = handle
        return True
    except Exception as e:
        print(f"[Main] Error creating Win32 mutex: {e}")
        return True

def check_single_instance(test_mode: bool = False) -> bool:
    """Returns True if this is the only instance, or False if another is already running."""
    if test_mode:
        return True

    # 1. First check Win32 Kernel Named Mutex
    if not acquire_win32_mutex():
        socket = QLocalSocket()
        socket.connectToServer(LOCAL_SERVER_NAME)
        if socket.waitForConnected(400):
            try:
                socket.write(b"EXPAND\n")
                socket.waitForBytesWritten(800)
                socket.disconnectFromServer()
            except Exception:
                pass
        return False

    # 2. Check if a local IPC server is already responding
    socket = QLocalSocket()
    socket.connectToServer(LOCAL_SERVER_NAME)
    if socket.waitForConnected(200):
        try:
            socket.write(b"EXPAND\n")
            socket.waitForBytesWritten(800)
            socket.disconnectFromServer()
        except Exception:
            pass
        return False

    return True

def setup_single_instance_server(notch_window, on_quit=None) -> QLocalServer:
    server = QLocalServer()
    QLocalServer.removeServer(LOCAL_SERVER_NAME)
    if server.listen(LOCAL_SERVER_NAME):
        def on_new_connection():
            client = server.nextPendingConnection()
            if client:
                def on_ready():
                    data = bytes(client.readAll()).decode("utf-8", errors="ignore")
                    if "QUIT" in data:
                        if on_quit:
                            on_quit()
                        else:
                            QApplication.quit()
                    elif "EXPAND" in data:
                        notch_window.expand()
                client.readyRead.connect(on_ready)
        server.newConnection.connect(on_new_connection)
    return server

def clean_end_task(notch_window=None, state_manager=None, tray=None, ipc_server=None):
    """
    Deterministic End-Task shutdown:
    1. Flushes and saves settings to config.json
    2. Hides notch window immediately
    3. Hides and cleans up system tray icon (eliminates ghost icons in Windows taskbar)
    4. Closes IPC server and removes named pipe
    5. Shuts down state manager and clears thread pool workers
    6. Calls os._exit(0) for hard process termination (no zombie tasks)
    """
    try:
        print("[Main] Executing clean end-task shutdown...")
        if notch_window:
            try:
                notch_window.save_all_settings()
                notch_window.hide()
            except Exception as e:
                print(f"[Main] Error saving settings on exit: {e}")

        if tray:
            try:
                tray.hide()
                tray.deleteLater()
            except Exception:
                pass

        if ipc_server:
            try:
                ipc_server.close()
                QLocalServer.removeServer(LOCAL_SERVER_NAME)
            except Exception:
                pass

        if state_manager:
            try:
                state_manager.shutdown()
            except Exception:
                pass

        try:
            from PyQt6.QtCore import QThreadPool
            QThreadPool.globalInstance().clear()
        except Exception:
            pass

        if notch_window:
            try:
                notch_window.close()
            except Exception:
                pass

        global WIN32_MUTEX_HANDLE
        if WIN32_MUTEX_HANDLE and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(WIN32_MUTEX_HANDLE)
                WIN32_MUTEX_HANDLE = None
            except Exception:
                pass
    except Exception as e:
        print(f"[Main] Error in clean_end_task: {e}")
    finally:
        os._exit(0)

def create_tray_icon(app, notch_win, app_icon: QIcon | None, on_quit=None):
    if app_icon and not app_icon.isNull():
        tray_icon = app_icon
    else:
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#1DB954"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 28, 28)
        p.setPen(QColor("#000000"))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "♫")
        p.end()
        tray_icon = QIcon(pix)

    tray = QSystemTrayIcon(tray_icon, app)
    tray.setToolTip("spfnotch")

    menu = QMenu()
    act_expand = menu.addAction("Tampilkan / Perbesar Notch")
    act_expand.triggered.connect(notch_win.expand)

    act_settings = menu.addAction("Pengaturan")
    def open_settings():
        notch_win.expand()
        notch_win.expanded_view.tabs.setCurrentIndex(3)
    act_settings.triggered.connect(open_settings)

    menu.addSeparator()
    act_quit = menu.addAction("Keluar")
    if on_quit:
        act_quit.triggered.connect(on_quit)
    else:
        act_quit.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.show()
    return tray

def main():
    test_mode = "--test" in sys.argv

    # Single-instance enforcement: if already running, trigger expand and exit
    if not check_single_instance(test_mode):
        print("[Main] spfnotch is already running. Focused existing instance.")
        sys.exit(0)

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("spfnotch")
    app.setQuitOnLastWindowClosed(False)

    app_icon = get_app_icon()
    if app_icon and not app_icon.isNull():
        app.setWindowIcon(app_icon)

    config_path = os.path.join(APP_DIR, "config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"[Main] Error loading config: {e}")

    # Core instances
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)

    # UI Window
    notch_window = NotchWindow(state_manager, image_cache, config)
    notch_window.show()

    # Shared end-task closure for deterministic exit
    tray = None
    ipc_server = None

    def do_end_task():
        clean_end_task(notch_window, state_manager, tray, ipc_server)

    notch_window.exit_requested_callback = do_end_task

    # System Tray
    tray = create_tray_icon(app, notch_window, app_icon, on_quit=do_end_task)

    # Single-instance local server to listen for new clicks/activations
    ipc_server = setup_single_instance_server(notch_window, on_quit=do_end_task)

    # Start state synchronization
    state_manager.start()

    # Ensure all settings are flushed on application exit
    app.aboutToQuit.connect(notch_window.save_all_settings)
    app.aboutToQuit.connect(state_manager.shutdown)

    if test_mode:
        print("[spfnotch] --test flag detected. Running 1.2s smoke test...")
        QTimer.singleShot(1200, lambda: (print("[spfnotch] Smoke test successful!"), do_end_task()))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
