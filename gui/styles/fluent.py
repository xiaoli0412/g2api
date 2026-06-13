"""Windows-native visual helpers for the PyQt shell."""

import ctypes
import math
import os
import random
from ctypes import wintypes

from PyQt5.QtCore import QRectF, QTimer, Qt
from PyQt5.QtGui import QColor, QMovie, QPainter, QPainterPath, QPixmap

from . import COLORS


DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWCP_ROUND = 2
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2
DWMSBT_TRANSIENTWINDOW = 3
DWMSBT_TABBEDWINDOW = 4
WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


class ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


def apply_window_material(window, material="mica"):
    """Apply a Windows 11 backdrop material to the main window."""
    material = (material or "mica").lower()
    applied = False
    try:
        hwnd = int(window.winId())
        dark = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark), ctypes.sizeof(dark)
        )
        corners = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corners), ctypes.sizeof(corners)
        )
        backdrop_kind = {
            "mica": DWMSBT_MAINWINDOW,
            "mica_alt": DWMSBT_TABBEDWINDOW,
            "acrylic": DWMSBT_TRANSIENTWINDOW,
            "solid": DWMSBT_NONE,
        }.get(material, DWMSBT_MAINWINDOW)
        backdrop = ctypes.c_int(backdrop_kind)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop), ctypes.sizeof(backdrop)
        )
        margins = MARGINS(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
            wintypes.HWND(hwnd), ctypes.byref(margins)
        )
        applied = True
    except Exception:
        applied = False

    try:
        hwnd = int(window.winId())
        accent_state = ACCENT_ENABLE_ACRYLICBLURBEHIND if material == "acrylic" else ACCENT_DISABLED
        accent = ACCENTPOLICY(accent_state, 2 if material == "acrylic" else 0, COLORS["acrylic_gradient"], 0)
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.byref(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)
        set_attr = ctypes.windll.user32.SetWindowCompositionAttribute
        set_attr(wintypes.HWND(hwnd), ctypes.byref(data))
        applied = applied or material == "acrylic"
    except Exception:
        if material == "acrylic":
            try:
                hwnd = int(window.winId())
                accent = ACCENTPOLICY(ACCENT_ENABLE_BLURBEHIND, 0, COLORS["acrylic_gradient"], 0)
                data = WINDOWCOMPOSITIONATTRIBDATA(
                    WCA_ACCENT_POLICY,
                    ctypes.cast(ctypes.byref(accent), ctypes.c_void_p),
                    ctypes.sizeof(accent),
                )
                ctypes.windll.user32.SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.byref(data))
                applied = True
            except Exception:
                pass
    return applied


def apply_acrylic(window):
    return apply_window_material(window, "acrylic")


def apply_mica(window):
    return apply_window_material(window, "mica")


def apply_solid(window):
    return apply_window_material(window, "solid")


def enable_frameless(window):
    window.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
    window.setAttribute(Qt.WA_TranslucentBackground, True)


def translucent_bg_qss(alpha=COLORS["acrylic_tint_alpha"]):
    return f"background-color: rgba(32, 32, 32, {alpha});"


class WindowsMaterialShellMixin:
    """Painter helper for a frameless Windows material shell."""

    _noise_tile = None

    def _paint_material_shell(self, painter, rect, image_path=None):
        radius = 8
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect.adjusted(0, 0, -1, -1)), radius, radius)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipPath(path)

        pixmap = self._background_pixmap(image_path)
        if pixmap and not pixmap.isNull():
            dynamic = bool(getattr(self, "window", None) and self.window.config.get("dynamic_background"))
            scale_mode = Qt.KeepAspectRatioByExpanding
            target_size = rect.size()
            if dynamic:
                target_size.setWidth(int(target_size.width() * 1.035))
                target_size.setHeight(int(target_size.height() * 1.035))
            scaled = self._cached_frosted_background(pixmap, target_size, scale_mode)
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            if dynamic:
                x += int(math.sin(getattr(self, "_motion_phase", 0) / 18) * 8)
                y += int(math.cos(getattr(self, "_motion_phase", 0) / 24) * 6)
            scaled = self._frosted_pixmap(scaled)
            painter.setOpacity(0.34)
            painter.drawPixmap(x, y, scaled)
            painter.setOpacity(1.0)
            painter.fillPath(path, QColor(32, 32, 32, self._photo_tint_alpha()))
        else:
            painter.fillPath(path, QColor(32, 32, 32, self._shell_tint_alpha()))

        noise = self._noise()
        if noise:
            painter.setOpacity(0.055)
            painter.drawTiledPixmap(rect, noise)
            painter.setOpacity(1.0)

        painter.setClipping(False)
        painter.setPen(QColor(COLORS["border"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)
        painter.restore()

    def _background_pixmap(self, image_path):
        if not image_path or not os.path.exists(image_path):
            return None
        if getattr(self, "_loaded_background_path", None) != image_path:
            self._loaded_background_path = image_path
            self._background_movie = None
            self._background_static = QPixmap()
            self._frosted_cache_key = None
            self._frosted_cache = QPixmap()
            lower = image_path.lower()
            if lower.endswith((".gif", ".webp")):
                movie = QMovie(image_path)
                if movie.isValid():
                    movie.frameChanged.connect(self._invalidate_background_frame)
                    movie.start()
                    self._background_movie = movie
            if self._background_movie is None:
                self._background_static = QPixmap(image_path)
        if getattr(self, "_background_movie", None):
            return self._background_movie.currentPixmap()
        return getattr(self, "_background_static", None)

    def _invalidate_background_frame(self):
        self._frosted_cache_key = None
        self.update()

    def _cached_frosted_background(self, pixmap, target_size, scale_mode):
        if pixmap.isNull():
            return pixmap
        cache_key = (
            getattr(self, "_loaded_background_path", ""),
            pixmap.cacheKey(),
            target_size.width(),
            target_size.height(),
            int(scale_mode),
        )
        if getattr(self, "_frosted_cache_key", None) == cache_key:
            cached = getattr(self, "_frosted_cache", None)
            if cached and not cached.isNull():
                return cached

        scaled = pixmap.scaled(target_size, scale_mode, Qt.SmoothTransformation)
        self._frosted_cache = self._frosted_pixmap(scaled)
        self._frosted_cache_key = cache_key
        return self._frosted_cache

    def _frosted_pixmap(self, pixmap):
        if pixmap.isNull():
            return pixmap
        small = pixmap.scaled(
            max(1, pixmap.width() // 20),
            max(1, pixmap.height() // 20),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        return small.scaled(pixmap.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def _start_motion_timer(self):
        self._motion_phase = 0
        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(250)
        self._motion_timer.timeout.connect(self._tick_motion)
        if getattr(self, "window", None) and self.window.config.get("dynamic_background"):
            self._motion_timer.start()

    def _tick_motion(self):
        if getattr(self, "window", None) and self.window.config.get("dynamic_background"):
            self._motion_phase += 1
            self.update()
        elif getattr(self, "_motion_timer", None) and self._motion_timer.isActive():
            self._motion_timer.stop()

    def _noise(self):
        if self._noise_tile is not None:
            return self._noise_tile
        tile = QPixmap(96, 96)
        tile.fill(Qt.transparent)
        rng = random.Random(11)
        painter = QPainter(tile)
        painter.setPen(QColor(255, 255, 255, 32))
        for _ in range(220):
            painter.drawPoint(rng.randrange(96), rng.randrange(96))
        painter.end()
        self._noise_tile = tile
        return tile

    def _material(self):
        if getattr(self, "window", None):
            return (self.window.config.get("window_material") or "mica").lower()
        return "mica"

    def _shell_tint_alpha(self):
        if self._material() == "acrylic":
            return COLORS["acrylic_tint_alpha"]
        if self._material() == "solid":
            return 255
        return COLORS["mica_tint_alpha"]

    def _photo_tint_alpha(self):
        if self._material() == "solid":
            return 230
        if self._material() == "acrylic":
            return COLORS["photo_tint_alpha"]
        return max(COLORS["photo_tint_alpha"], 196)

    def _paint_acrylic_shell(self, painter, rect, image_path=None):
        self._paint_material_shell(painter, rect, image_path)


AcrylicShellMixin = WindowsMaterialShellMixin
