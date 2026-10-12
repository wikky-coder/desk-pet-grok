"""Edge fit: every lying pose drawn on a fake edge line -> _gen25d/rounds/edgefit/ (+ prints the measured baseline offset)."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DESK_PET_GROK_CONFIG_DIR"] = "/tmp/dpg-render-cfg"
sys.path.insert(0, "tests")
from pathlib import Path
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from test_lounge_pet import _lie
from desk_pet_grok import loungeart

OUT = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "edgefit"
POSES = [("base", "base", (1, 0, 0)), ("base", "half", (1, .5, 0)), ("base", "yawn", (1, 0, 1)), ("base", "sleep", (1, 1, 0)),
         ("side", "side", (1, 0, 0)), ("chin", "chin", (1, 0, 0)), ("stretch", "stretch", (1, 0, 0)), ("curl", "curl", (1, 1, 0))]


def measure(win, pet, var, pose, H):
    pet._var_on = True
    pet._var_from = pet._var_to = var; pet._var_t = 1.0
    pet._var_next = 1e9
    pet.set_lounge(pose)
    pet._var_from = pet._var_to = var; pet._var_t = 1.0
    for _ in range(3): pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    pet._var_from = pet._var_to = var; pet._var_t = 1.0
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    ptr = img.constBits(); a = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(), 3]
    need = max(2, int(loungeart.BASELINE_MIN_FRAC * pet._main_art().fw * (H / 940.0)))
    rows = np.where((a > 128).sum(1) >= need)[0]
    edge = H * (1 - loungeart.EDGE_UP)
    return img, int(rows.max()) + 1 - edge, edge


def main(H=500):
    win, drv = _lie(Path(tempfile.mkdtemp()))
    win._motion_timer.stop(); win.show()
    win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000); win.resize(int(H * 0.7659), H); app.processEvents(); win._pet.resize(win.size())
    pet = win._pet
    tiles, res = [], {}
    for var, name, pose in POSES:
        img, dev, edge = measure(win, pet, var, pose, H)
        res[f"{var}/{name}"] = dev
        bg = QImage(img.size(), QImage.Format.Format_ARGB32); bg.fill(QColor(235, 235, 240))
        p = QPainter(bg); p.fillRect(0, int(round(edge)), img.width(), img.height(), QColor(150, 150, 160)); p.drawImage(0, 0, img)
        p.setPen(QPen(QColor(255, 0, 0), 1)); p.drawLine(0, int(round(edge)), img.width(), int(round(edge))); p.end()
        f = OUT / f"edge_{var}_{name}.png"; OUT.mkdir(parents=True, exist_ok=True); bg.save(str(f)); tiles.append(Image.open(f).convert("RGB"))
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * 4, h * 2)); [sheet.paste(t, ((i % 4) * w, (i // 4) * h)) for i, t in enumerate(tiles)]
    sheet.save(OUT / "edgefit_sheet.png")
    for k, v in res.items(): print(f"{k:16s} baseline - edge = {v:+.1f} px  (H={H})")
    return res


if __name__ == "__main__":
    main()
