import collections
import urllib.request
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QBitmap
from PyQt6.QtCore import Qt

class ImageDownloadWorker(QRunnable):
    def __init__(self, url: str, callback):
        super().__init__()
        self.url = url
        self.callback = callback

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'spfnotch/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = response.read()
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    self.callback(self.url, pixmap)
                else:
                    self.callback(self.url, None)
        except Exception as e:
            self.callback(self.url, None)

class ImageCache(QObject):
    image_loaded = pyqtSignal(str, QPixmap)

    def __init__(self, max_size: int = 15):
        super().__init__()
        self.max_size = max_size
        self._cache = collections.OrderedDict()
        self._thread_pool = QThreadPool.globalInstance()
        self._in_progress = set()

    def get_pixmap(self, url: str, rounded_radius: int = 8, size: int = 64) -> QPixmap | None:
        """
        Retrieves a cached, rounded pixmap, or schedules background download.
        """
        if not url:
            return None

        cache_key = f"{url}_{size}_{rounded_radius}"
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        if url not in self._in_progress:
            self._in_progress.add(url)
            worker = ImageDownloadWorker(url, self._on_download_complete)
            self._thread_pool.start(worker)

        return None

    def _on_download_complete(self, url: str, raw_pixmap: QPixmap | None):
        if url in self._in_progress:
            self._in_progress.remove(url)

        if raw_pixmap and not raw_pixmap.isNull():
            # Create versions
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
