"""Offscreen check of the bubble tail on every side / clamped near corners -> _gen25d/rounds/bubblefit/."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication, QWidget
import desk_pet_grok.bubble as B
app = QApplication.instance() or QApplication([])
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "bubblefit"
SCR = (0.0, 0.0, 900.0, 600.0)
B.screen_rects = lambda: [SCR]
cases = {"center_above": (320, 300), "top_below": (320, 0), "left_edge_above": (0, 300), "right_edge_above": (900 - 263, 300),
         "topleft_corner": (0, 0), "bottomright_corner": (900 - 263, 600 - 220)}
W, H = 900, 600
for name, (ax, ay) in cases.items():
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(225, 233, 240))
    a = QWidget(); a.setGeometry(ax, ay, 263, 220)
    b = B.BubbleWidget(); b.show_text("本喵在这里陪着主人，今天也要加油喵。"); b.reposition_above(a)
    p = QPainter(img)
    p.setBrush(QColor(255, 200, 150, 160)); p.setPen(QPen(QColor(200, 120, 60), 1)); p.drawRect(ax, ay, 263, 220)
    p.drawText(ax + 6, ay + 14, "pet window")
    p.drawImage(b.x(), b.y(), b.grab().toImage())
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(220, 0, 0), 2)); p.drawRect(0, 0, W - 1, H - 1)
    p.end()
    img.save(str(out / f"{name}.png"))
    print(name, b._tail_edge, b.geometry().getRect())
