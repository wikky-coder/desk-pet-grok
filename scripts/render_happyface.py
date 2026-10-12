"""Offscreen keyframes of the standing head-pat (happy face layer) -> _gen25d/rounds/happyface/."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
from pathlib import Path
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow
tag = sys.argv[1] if len(sys.argv) > 1 else "v1"
H = int(sys.argv[2]) if len(sys.argv) > 2 else 470
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "happyface"
win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "window_height": H})
win._motion_timer.stop(); win.show(); win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000); win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
def step(n, dt=1 / 60):
    for _ in range(n):
        pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
def shot(name):
    for _ in range(2): app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end()
    bg.save(str(out / f"pat_{tag}_{name}.png")); print(name, round(pet._happy, 2), round(pet._pat, 2))
step(120); shot("0_open")
pet.set_petting(True)
for i, n in enumerate((6, 6, 6, 30, 60)):  # ~0.1, 0.2, 0.3, .. s
    step(n); shot(f"{i+1}_on")
pet.set_petting(False)
for i, n in enumerate((6, 9, 30, 90)):
    step(n); shot(f"{i+6}_off")
# fine fade frames (every 2 frames) for the wipe check
pet.set_petting(False); step(120)
pet.set_petting(True)
for i in range(1, 8):
    step(2); shot(f"fade_{i}")
