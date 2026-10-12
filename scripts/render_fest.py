"""v4-6: render each prop mode on the real pet -> _gen25d/rounds/v4/fest_*.png + sheet"""
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
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "v4"
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
from desk_pet_grok import holidays
ims = []
for k in holidays.FESTIVALS:
    pet.set_holiday(k); step(100); pet.grab()
    im = shot(); im.save(out / f"fest_{k}.png"); ims.append(im)
w, h = ims[0].size
sheet = Image.new("RGB", (w * 4, h * 2))
for i, im in enumerate(ims): sheet.paste(im, ((i % 4) * w, (i // 4) * h))
sheet.save(out / "fest_all.png")
pet.set_holiday(None); step(60)
gi = []
for kind, face in (("sun", "happy"), ("bowl", "happy"), ("cup", None), ("moon", "happy"), ("moon_zzz", "sleepy"), ("zzz", "sleepy")):
    pet._expr = None; pet._greet_fx.start(kind)
    pet.greet(kind, face, hold=9); step(75)
    gi.append(shot())
sheet = Image.new("RGB", (w * 3, h * 2))
for i, im in enumerate(gi): sheet.paste(im, ((i % 3) * w, (i // 3) * h))
sheet.save(out / "greet_all.png"); print(sheet.size)
