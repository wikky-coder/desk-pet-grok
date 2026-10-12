"""v4-3: render the clinging frames of the real pet; crop at the screen border (what the user sees) -> _gen25d/rounds/v4/cling_view.png"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
from pathlib import Path
from PIL import Image, ImageDraw
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow
out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "v4"
H = 700
win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "cling_edge": True})
win._motion_timer.stop(); win.show(); win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000)
win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
pet = win._pet
def step(n, dt=1 / 60):
    for _ in range(n): pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
import time
def shot():
    pet.grab(); time.sleep(0.5)  # flush the rig<->sheet cross-fade (wall clock) before the real grab
    for _ in range(2): app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(236, 238, 242))
    p = QPainter(bg); p.drawImage(0, 0, img); p.end()
    p = Path("/tmp/_shot.png"); bg.save(str(p)); return Image.open(p).convert("RGB")
step(60)
tiles = []
for side in (-1, 1):
    for peek in (False, True):
        pet.set_cling(side, peek); step(90)
        im = shot(); cx = int(pet.cling_cut_x(float(H)))
        d = ImageDraw.Draw(im); 
        # what is visible on screen: left border -> keep x>=cx ; right border -> keep x<=cx
        vis = im.crop((cx, 0, im.width, H)) if side < 0 else im.crop((0, 0, cx, H))
        tiles.append(vis); im.save(out / f"cling_{'L' if side < 0 else 'R'}_{'peek' if peek else 'idle'}.png")
W = sum(t.width for t in tiles) + 10 * 5
sheet = Image.new("RGB", (W, H), (120, 125, 140)); x = 10
for t in tiles: sheet.paste(t, (x, 0)); x += t.width + 10
sheet.save(out / "cling_view.png"); print(sheet.size)
