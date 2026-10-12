"""F7: offscreen renders of every lying pose variant (+ eyes half/sleep, head-pat, and the duck-out/pop-in switch) -> _gen25d/rounds/f7/."""
import math, os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
sys.path.insert(0, "tests")
from pathlib import Path
from PIL import Image
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from test_lounge_pet import _lie, Clock, _zone_center
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "f7"
win, drv = _lie(Path(tempfile.mkdtemp()))
win._motion_timer.stop(); win.show()
H = 700
win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000); win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
pet.set_lounge_variants(True)
c = Clock(win, drv)
for _ in range(60): c.step(win.x() + 900, win.y() - 300)

def shot(name):
    for _ in range(2): app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end(); bg.save(str(out / f"{name}.png")); return Image.open(out / f"{name}.png").convert("RGB")

def settle(n=40):
    for _ in range(n): c.step(win.x() + 900, win.y() - 300)

shots = {}
for v in ("base", "side", "chin", "stretch", "curl"):
    pet._var_from = pet._var_to = v; pet._var_t = 1.0
    pet.set_lounge((1.0, 1.0 if v == "curl" else 0.0, 0.0))  # curl is the asleep pose (she would wake out of it otherwise)
    [pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False) for _ in range(40)]; shots[v] = shot(f"var_{v}")
pet.set_lounge((1.0, 0.0, 0.0))
w, h = shots["base"].size
sheet = Image.new("RGB", (w * 5, h)); [sheet.paste(im, (i * w, 0)) for i, im in enumerate(shots.values())]
sheet.save(out / "variants_sheet.png")
# eyes droop on side / chin
for v in ("side", "chin"):
    pet._var_from = pet._var_to = v; pet._var_t = 1.0
    row = []
    for d in (0.0, 0.5, 1.0):
        pet.set_lounge((1.0, d, 0.0)); pet._var_from = pet._var_to = v; pet._var_t = 1.0; [pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False) for _ in range(4)]; pet._var_from = pet._var_to = v; pet._var_t = 1.0; row.append(shot(f"tmp_{v}_{d}"))
    pet.set_lounge((1.0, 0.0, 0.0))
    s = Image.new("RGB", (w * 3, h)); [s.paste(im, (i * w, 0)) for i, im in enumerate(row)]
    s.save(out / f"eyes_{v}.png")
# switch strip base -> side
pet._var_from = pet._var_to = "base"; pet._var_t = 1.0; settle()
pet._var_start("side"); strip = []
for i in range(8):
    for _ in range(5): pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    strip.append(shot(f"tmp_sw{i}")); print("t", round(pet._var_t, 2))
s = Image.new("RGB", (w * 4, h * 2)); [s.paste(im, ((i % 4) * w, (i // 4) * h)) for i, im in enumerate(strip)]
s.save(out / "switch_base_to_side.png")
for f in out.glob("tmp_*"): f.unlink()
