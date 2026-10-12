"""v4b: render each prop mode (two hands check) on the real pet -> _gen25d/rounds/v4/work_*.png + sheet"""
import os, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
from pathlib import Path
from PIL import Image
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "v4b"
H = 700
win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True})
win._motion_timer.stop(); win.show(); win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000)
win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
def step(n, dt=1 / 60):
    for _ in range(n): pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
def shot():
    pet.grab(); time.sleep(0.5)
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end()
    p = Path("/tmp/_shot.png"); bg.save(str(p)); return Image.open(p).convert("RGB")
step(90)
ims = []
for m in (None, "read", "code", "terminal", "draw"):
    pet.set_work(m); step(120 if m else 150)
    im = shot(); im.save(out / f"hands_{m or 'none'}.png"); ims.append(im)
w, h = ims[0].size
sheet = Image.new("RGB", (w * 5, h))
for i, im in enumerate(ims): sheet.paste(im, (i * w, 0))
sheet.save(out / "hands_modes.png"); print(sheet.size)
