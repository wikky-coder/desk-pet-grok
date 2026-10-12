"""Offscreen keyframes of a head-pat while lying on an edge -> _gen25d/rounds/lounge_pet/."""
import math, os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
sys.path.insert(0, "tests")
from pathlib import Path
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from test_lounge_pet import _lie, Clock, _zone_center
import tempfile
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "lounge_pet"
out.mkdir(parents=True, exist_ok=True)
win, drv = _lie(Path(tempfile.mkdtemp()))
win.apply_height(360, persist=False)
win._motion_timer.stop()
win.show()
c = Clock(win, drv)
for _ in range(90): c.step(win.x() + 900, win.y() - 300)
cx, cy, z = _zone_center(win)
DPR_SCALE = 1

def shot(name):
    print(name, 'pat', round(win._pet.pat_amount(),2), 'droop', round(drv.lounge.droop,2), 'state', drv.lounge.state)
    for _ in range(2):
        app.processEvents()
    pm = win._pet.grab()
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end()
    bg.save(str(out / f"{name}.png"))

for _ in range(30): c.step(cx + 300, cy - 250)
shot("0_before")
marks = {3: "1_pat_ears", 12: "2_pat_half", 21: "3_pat_closing", 30: "4_pat_closed", 60: "5_pat_closed_later"}
t0 = None
for i in range(1, 140):
    c.step(cx + 30 * math.sin(2 * math.pi * 3 * i / 30), cy)
    if t0 is None and win._pat_now:
        t0 = i
    if t0 is not None and (i - t0) in marks:
        shot(marks[i - t0])
for j in range(1, 100):
    c.step(cx + 300, cy - 250)
    if j == 8: shot("6_release_opening")
    if j == 90: shot("7_after")

