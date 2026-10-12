"""fallfix2: real running path (PetWindow + LoungeDriver + FakeProbe edge drop), user's settings (classic render, lounge_variants, mood, look_at_mouse,
tail_boost, rig_auto off); renders every tick of lie -> fall -> land/stand, reports frames with stray small blobs (eyes alone).
usage: render_fall2.py <tag> [variant] [sleep]"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg2"
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow
from desk_pet_grok.focus_probe import FakeProbe, FieldGeom
import cv2

THR = 40
MASKED = bool(int(os.environ.get('MASKED', '0')))

def blobs(img, thr=None):
    a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(), 3]
    thr = THR if thr is None else thr
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > thr).astype(np.uint8), connectivity=8)
    areas = st[1:, cv2.CC_STAT_AREA]
    if len(areas) == 0: return 0, []
    big = int(areas.max())
    return big, sorted(int(x) for x in areas if x < 0.3 * big and x > 6)

def run(tag, variant=None, sleep=False, outdir=None, H=220, save=True):
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "lounge_variants": True, "mood": True, "look_at_mouse": True,
                                                            "tail_boost": True, "rig_auto": False, "window_height": H})
    win._motion_timer.stop(); win.show(); app.processEvents()
    win.set_lounge(True, persist=False)
    pet, drv = win._pet, win._lounge
    drv.probe = FakeProbe([FieldGeom(200, 600, 900, 500)])
    win.move(500, 600 - win.height() + 10)
    assert drv.on_drop()
    pet.set_gaze_enabled(True)
    def tick(dt=1 / 60):
        drv._poll(); drv.tick(dt)
        pet.set_gaze(0.7, -0.4)
    for _ in range(60 * 3): tick()
    if variant:
        pet._var_start(variant, instant=True)
        for _ in range(30): tick()
    if sleep:
        drv.lounge.t_lounge = 1e6
        for _ in range(60 * 4): tick()
    # the edge vanishes -> she falls to the floor
    drv.probe = FakeProbe([FieldGeom(200, 1400, 900, 500)])
    frames, stats = [], []
    for i in range(60 * 3):
        tick()
        img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        big, small = blobs(img)
        stats.append((i, drv.lounge.state, round(pet._lounge[0], 2) if pet._lounge else None, big, small))
        if save:
            if MASKED:  # what the user actually sees: the window mask cuts everything that is not (nearly) opaque
                img = img.copy()
                ptr = np.frombuffer(img.bits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)
                ptr[ptr[:, :, 3] < 128] = 0
            bg = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied); bg.fill(QColor(205, 222, 235))
            p = QPainter(bg); p.drawImage(0, 0, img); p.end()
            f = Path("/tmp/_shot_fall2.png"); bg.save(str(f)); frames.append((i, Image.open(f).convert("RGB")))
        if drv.lounge.state == "idle" and i > 30: break
    win.close()
    if save and outdir:
        w, h = frames[0][1].size
        step = max(1, len(frames) // 36)
        sel = frames[::step]
        cols = 9; rows = (len(sel) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows), (255, 255, 255))
        for n, (i, im) in enumerate(sel):
            d = ImageDraw.Draw(im); d.text((4, 4), str(i), fill=(0, 0, 0))
            sheet.paste(im, ((n % cols) * w, (n // cols) * h))
        for i, im in frames: im.save(outdir / f"{tag}_{i:03d}.png")
        sheet.save(outdir / f"{tag}_sheet.png")
    return stats

if __name__ == "__main__":
    tag = sys.argv[1]; var = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    sl = len(sys.argv) > 3
    out = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "fallfix2"; out.mkdir(parents=True, exist_ok=True)
    st = run(tag, var, sl, out)
    bad = [s for s in st if s[4]]
    print(len(st), "frames;", len(bad), "with stray blobs")
    for s in bad[:40]: print(s)
