"""v4-2: render each anger stage of the real pet (offscreen) -> _gen25d/rounds/v4/shake_stage_*.png + sheet."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
from pathlib import Path
from PIL import Image
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "v4"
H = 700
win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "shake_anger": True})
win._motion_timer.stop(); win.show(); win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000)
win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
def step(n, dt=1 / 60):
    for _ in range(n): pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
def shot():
    for _ in range(2): app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end()
    p = Path("/tmp/_shot.png"); bg.save(str(p)); return Image.open(p).convert("RGB")
step(120)
ims = []
for st in (0, 1, 2, 3, 4, 5):
    pet.set_anger(st); step(100 if st != 4 else 130)
    im = shot(); im.save(out / f"shake_stage_{st}.png"); ims.append(im)
w, h = ims[0].size
sheet = Image.new("RGB", (w * 6, h))
for i, im in enumerate(ims): sheet.paste(im, (i * w, 0))
sheet.save(out / "shake_stages.png")
print(sheet.size)
