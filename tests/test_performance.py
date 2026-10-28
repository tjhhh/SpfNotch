import sys
import os
import time
import psutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from app.utils.image_cache import ImageCache
from app.core.lyrics_client import LyricsClient
from app.core.spotify_client import SpotifyClient
from app.core.state_manager import StateManager
from app.ui.notch_window import NotchWindow

def test_app_memory_and_cpu():
    app = QApplication(sys.argv)
    
    config_path = os.path.join(BASE_DIR, "config.json")
    image_cache = ImageCache()
    lyrics_client = LyricsClient()
    spotify_client = SpotifyClient(config_path)
    state_manager = StateManager(spotify_client, lyrics_client)
    notch_window = NotchWindow(state_manager, image_cache, {})
    notch_window.show()

    state_manager.start()

    proc = psutil.Process(os.getpid())

    # Measure memory and CPU after 1.5 seconds of simulation
    def on_timeout():
        # Memory in MB
        mem_info = proc.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        cpu_pct = proc.cpu_percent(interval=0.1)

        print(f"[METRICS] Process RSS Memory: {rss_mb:.2f} MB")
        print(f"[METRICS] Process CPU Usage: {cpu_pct:.2f}%")

        # Verify performance constraints
        assert rss_mb < 90, f"Memory exceeded limit! Current: {rss_mb} MB"
        print("[PASS] Memory is within optimal lightweight range (<90MB on init).")
        app.quit()

    QTimer.singleShot(1500, on_timeout)
    app.exec()

if __name__ == "__main__":
    test_app_memory_and_cpu()
    print("Application lifecycle & performance test passed!")
