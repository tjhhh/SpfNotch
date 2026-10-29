import collections
import hashlib
import os
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable, Qt
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath

class ImageDownloadWorker(QRunnable):
    def __init__(self, url: str, disk_path: str, callback):
        super().__init__()
        self.url = url
        self.disk_path = disk_path
        self.callback = callback

    def run(self):
        try:
            headers = {'User-Agent': 'spfnotch/1.0 (Spotify Dynamic Notch for Windows)'}
            resp = requests.get(self.url, headers=headers, timeout=10)
            if resp.status_code == 200 and resp.content:
                # Save to persistent local disk cache
                try:
                    os.makedirs(os.path.dirname(self.disk_path), exist_ok=True)
                    with open(self.disk_path, "wb") as f:
                        f.write(resp.content)
                except Exception as fe:
                    print(f"[ImageCache] Error saving disk cache: {fe}")

                # Safely load into QImage (100% thread-safe in background workers)
                img = QImage()
                if img.loadFromData(resp.content):
                    pixmap = QPixmap.fromImage(img)
                    self.callback(self.url, pixmap)
                    return
                else:
                    print(f"[ImageCache] Failed to decode image bytes from {self.url}")
            else:
                print(f"[ImageCache] HTTP {resp.status_code} fetching {self.url}")
            self.callback(self.url, None)
        except Exception as e:
            print(f"[ImageCache] Download error for {self.url}: {e}")
            self.callback(self.url, None)

class ImageCache(QObject):
    image_loaded = pyqtSignal(str, QPixmap)

    def __init__(self, max_size: int = 25):
        super().__init__()
        self.max_size = max_size
        self._cache = collections.OrderedDict()
        self._thread_pool = QThreadPool.globalInstance()
        self._in_progress = set()

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.disk_cache_dir = os.path.join(base_dir, ".cache", "covers")

    def _get_disk_cache_path(self, url: str) -> str:
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return os.path.join(self.disk_cache_dir, f"{url_hash}.png")

    def get_pixmap(self, url: str, rounded_radius: int = 8, size: int = 64) -> QPixmap | None:
        """
        Retrieves a cached, rounded pixmap from RAM or disk, or schedules background download.
        """
        if not url:
            return None

        cache_key = f"{url}_{size}_{rounded_radius}"
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        disk_path = self._get_disk_cache_path(url)
        if os.path.exists(disk_path):
            raw = QPixmap(disk_path)
            if raw and not raw.isNull():
                return self.process_and_cache(url, raw, rounded_radius, size)

        if url not in self._in_progress:
            self._in_progress.add(url)
            worker = ImageDownloadWorker(url, disk_path, self._on_download_complete)
            self._thread_pool.start(worker)

        return None

    def _on_download_complete(self, url: str, raw_pixmap: QPixmap | None):
        if url in self._in_progress:
            self._in_progress.remove(url)

        if raw_pixmap and not raw_pixmap.isNull():
            self.image_loaded.emit(url, raw_pixmap)

    def process_and_cache(self, url: str, raw_pixmap: QPixmap, rounded_radius: int = 8, size: int = 64) -> QPixmap:
        cache_key = f"{url}_{size}_{rounded_radius}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        scaled = raw_pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        
        # Create rounded pixmap
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, rounded_radius, rounded_radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled)
        painter.end()

        # Evict oldest if exceeding max_size
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[cache_key] = rounded
        return rounded
