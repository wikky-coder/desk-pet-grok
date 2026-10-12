"""Shared look for the chat card + speech bubble: cream card, maid-outfit navy/blue accents, rounded fonts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

NAVY = "#2f3f6e"
BLUE = "#6aa6e8"
BLUE_DARK = "#4f8fd8"
BLUE_PALE = "#d7e8fc"
CREAM_RGBA = "rgba(255, 251, 243, 240)"
INK = "#2b3350"

AVATAR_PATH = Path(__file__).resolve().parents[1] / "assets" / "ui" / "avatar.png"
PET_NAME = "小 Grok"

_ROUND_FAMILIES = [
    "Hiragino Maru Gothic ProN",
    "Arial Rounded MT Bold",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
]


def round_font(point_size: int = 11, bold: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(_ROUND_FAMILIES)
    font.setPointSize(point_size)
    font.setBold(bold)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def circle_avatar(size: int) -> QPixmap | None:
    """Her face from assets/ui/avatar.png cropped to a circle with a white ring; None if the asset is missing."""
    src = QPixmap(str(AVATAR_PATH))
    if src.isNull():
        return None
    scale = 2
    px = size * scale
    src = src.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    ring = 3 * scale
    p.setBrush(QColor("white"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(0, 0, px, px))
    from PySide6.QtGui import QPainterPath

    path = QPainterPath()
    path.addEllipse(QRectF(ring, ring, px - 2 * ring, px - 2 * ring))
    p.setClipPath(path)
    p.drawPixmap(0, 0, src)
    p.end()
    out.setDevicePixelRatio(scale)
    return out


def paw_pixmap(size: int, color: str = "#ffffff") -> QPixmap:
    """Cat-paw glyph: one big pad + four toe beans."""
    scale = 2
    px = size * scale
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    s = float(px)
    p.drawEllipse(QRectF(s * 0.26, s * 0.47, s * 0.48, s * 0.40))  # main pad
    for cx, cy, rw, rh in ((0.17, 0.42, 0.17, 0.22), (0.37, 0.19, 0.18, 0.24), (0.63, 0.19, 0.18, 0.24), (0.83, 0.42, 0.17, 0.22)):
        p.drawEllipse(QPointF(s * cx, s * cy), s * rw / 2 + 1, s * rh / 2 + 1)
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def draw_soft_shadow(p: QPainter, rect: QRectF, radius: float, spread: int = 8, alpha: int = 5) -> None:
    """Cheap blur-free shadow for translucent top-level windows: stacked faint rounded rects."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(spread, 0, -1):
        p.setBrush(QColor(40, 55, 100, alpha))
        p.drawRoundedRect(rect.adjusted(-i, -i + 2, i, i + 2), radius + i, radius + i)
    p.restore()
