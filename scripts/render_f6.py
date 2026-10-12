"""F6: one offscreen render per mood (full figure + face zoom) and a calm->surprised fade strip -> _gen25d/rounds/f6/."""
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
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "f6"
H = 940
win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "mood": True})
win._motion_timer.stop(); win.show(); win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000)
win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
def step(n, dt=1 / 60):
    for _ in range(n): pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
def shot(path):
    for _ in range(2): app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end(); bg.save(str(path)); return Image.open(path)
step(120)
frames = {}
for m in ("calm", "happy", "sleepy", "annoyed", "surprised", "pouty"):
    pet.set_mood(m); step(60)
    frames[m] = shot(out / f"mood_{m}.png")
w, h = frames["calm"].size
box = (int(w * .12), int(h * .08), int(w * .88), int(h * .55))
sheet = Image.new("RGB", ((box[2] - box[0]) * 3, (box[3] - box[1]) * 2))
for i, m in enumerate(frames):
    sheet.paste(frames[m].crop(box).convert("RGB"), ((i % 3) * (box[2] - box[0]), (i // 3) * (box[3] - box[1])))
sheet.save(out / "moods_sheet.png")
full = Image.new("RGB", (w * 6, h))
for i, m in enumerate(frames): full.paste(frames[m].convert("RGB"), (i * w, 0))
full.save(out / "moods_full_figure.png")
pet.set_mood("calm"); step(60)
strip = []
pet.set_mood("surprised")
for i in range(9):
    step(3); strip.append(shot(out / "_tmp.png").crop(box).convert("RGB")); print(i, round(pet._mood_t, 2))
os.remove(out / "_tmp.png")
s2 = Image.new("RGB", ((box[2] - box[0]) * 3, (box[3] - box[1]) * 3))
for i, im in enumerate(strip): s2.paste(im, ((i % 3) * im.width, (i // 3) * im.height))
s2.save(out / "fade_calm_to_surprised.png")
