"""fall fix: render the lie-down -> fall -> stand-up hand-off frame by frame (surprised face + happy face active, as in a real fall)
-> _gen25d/rounds/fallfix/<tag>_*.png and a contact sheet. usage: render_fall.py <tag>"""
import os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
from pathlib import Path
from PIL import Image, ImageDraw
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow
tag = sys.argv[1] if len(sys.argv) > 1 else "after"
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "fallfix"
H = 520
win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "mood": True})
win._motion_timer.stop(); win.show(); win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000)
win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
def step(n=1, dt=1 / 60):
    for _ in range(n): pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
def shot():
    pet.grab(); time.sleep(0.02)
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end()
    f = Path("/tmp/_shot_fall.png"); bg.save(str(f)); return Image.open(f).convert("RGB")
step(60)
pet.set_lounge((0.0, 0.0, 0.0)); step(5)
frames = []
# lie down fully
for i in range(60):
    pet.set_lounge((min(1.0, i / 40.0), 0.0, 0.0)); step()
# fall: she is thrown up (lift), wakes (loaf 1 -> 0 while falling), face = surprised, happy layer partly on
pet.set_mood("surprised") if hasattr(pet, "set_mood") else None
pet._mood_on = True; pet._apply_face("surprised")
pet._happy = 0.0
for i in range(70):
    u = i / 69.0
    loaf = max(0.0, 1.0 - u * 1.6)
    pet.set_lounge((loaf, 0.0, 0.0)); pet.set_fall(min(1.0, u * 3), 1.0, 1.0)
    pet._happy = 0.7 if 20 < i < 50 else 0.0
    step()
    if i % 4 == 0 and i < 44:
        frames.append((i, shot()))
w, h = frames[0][1].size
cols = 6; rows = (len(frames) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), (255, 255, 255))
for n, (i, im) in enumerate(frames):
    d = ImageDraw.Draw(im); d.text((6, 6), str(i), fill=(0, 0, 0))
    sheet.paste(im, ((n % cols) * w, (n // cols) * h))
    im.save(out / f"{tag}_{i:02d}.png")
sheet.save(out / f"{tag}_sheet.png"); print(sheet.size, len(frames))
