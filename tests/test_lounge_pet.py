"""Head-pat while lying on an edge / the Dock: zone follows the lying head, she stays lying, eyes close, no dozing."""

from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from PySide6.QtWidgets import QApplication

from desk_pet_grok import loungeart, partrig, petting
from desk_pet_grok import lounge as L
from desk_pet_grok.focus_probe import FakeProbe, FieldGeom
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


_WINS: list = []


@pytest.fixture(autouse=True)
def _restore_puppet_globals():
    from desk_pet_grok import puppet
    saved = puppet.STRIDE_PX_PER_FRAME
    yield
    puppet.STRIDE_PX_PER_FRAME = saved


needs_art = pytest.mark.skipif(not (partrig.available() and loungeart.available()), reason="lounge assets missing")


def test_head_zone_covers_whole_head_with_margin_but_not_the_body():
    x0, y0, x1, y1 = loungeart.HEAD_ZONE_FRAME
    # head incl. ears + headband in the 640x656 frame: x 125..565, y 33..420
    hx0, hy0, hx1, hy1 = 125.0, 33.0, 565.0, 420.0
    assert x0 <= hx0 - 0.15 * (hx1 - hx0) and x1 >= hx1 + 0.15 * (hx1 - hx0) - 1
    assert y0 <= hy0 - 0.15 * (hy1 - hy0) and y1 >= hy1 + 0.10 * (hy1 - hy0)
    assert y1 <= 480  # forearms / lower body start around y 440-470: the zone stops there
    w, h = 263, 220
    zx0, zy0, zx1, zy1 = loungeart.head_zone(w, h)
    assert 0 <= zx0 < zx1 <= w and 0 <= zy0 < zy1 <= h
    k = h / 940.0
    ledge = h * (1 - loungeart.FOOT_PAD) + 0.008 * h
    assert zy1 < ledge - 150 * k  # clearly above the ledge: lower body is not inside
    sx0, sy0, sx1, sy1 = petting.head_zone(0, 0, w, h)
    assert (zx1 - zx0) > (sx1 - sx0) * 0.9


@pytest.fixture(autouse=True)
def _restore_cfg_env():
    _WINS.clear()
    old = os.environ.get("DESK_PET_GROK_CONFIG_DIR")
    yield
    for w in _WINS:
        w._motion_timer.stop()
        w.close()
        w.deleteLater()
    _WINS.clear()
    if old is None:
        os.environ.pop("DESK_PET_GROK_CONFIG_DIR", None)
    else:
        os.environ["DESK_PET_GROK_CONFIG_DIR"] = old


def _lie(tmp_path):
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "lounge": True, "window_height": 220})
    drv = win._lounge
    drv.probe = FakeProbe([FieldGeom(200, 500, 900, 600)])
    win.move(500, 500 - win.height() + 10)
    assert drv.on_drop()
    for _ in range(120):
        drv._poll()
        drv.tick(1 / 30)
    assert drv.lounge.state == "lounge_loop" and win._pet.lounging()
    _WINS.append(win)
    return win, drv


class Clock:
    def __init__(self, win, drv):
        self.win, self.drv, self.t = win, drv, 1000.0

    def step(self, x, y, dt=1 / 30):
        self.t += dt
        self.win.feed_cursor(self.t, x, y)
        self.drv._poll()
        self.drv.tick(dt)

    def zigzag(self, cx, cy, seconds=1.2, amp=40.0, hz=3.0):
        n = int(seconds * 30)
        for i in range(n):
            self.step(cx + amp * math.sin(2 * math.pi * hz * i / 30), cy)


def _zone_center(win):
    z = win._pet.lounge_head_zone(win.width(), win.height())
    assert z is not None
    return win.x() + (z[0] + z[2]) / 2, win.y() + (z[1] + z[3]) / 2, z


@needs_art
def test_zigzag_over_lying_head_triggers_and_keeps_lying(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    said = []
    win.lounge_say.connect(said.append)
    c = Clock(win, drv)
    cx, cy, _ = _zone_center(win)
    c.zigzag(cx, cy, 1.5, amp=30)
    assert win._pat_now
    assert drv.lounge.state == "lounge_loop" and drv.lounge.petting
    assert said == ["pet_head"]
    c.zigzag(cx, cy, 1.0, amp=30)
    assert said == ["pet_head"]  # 20 s cooldown
    assert drv.lounge.droop > 0.9  # eyes closed (sleep frame) while enjoying
    assert win._pet.lounging()
    # stop: she recovers the awake lie
    for _ in range(150):
        c.step(cx + 400, cy - 300)
    assert not win._pat_now and drv.lounge.droop < 0.05 and drv.lounge.state == "lounge_loop"


@needs_art
def test_standing_head_spot_does_not_trigger_when_lying(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    c = Clock(win, drv)
    sx0, sy0, sx1, sy1 = petting.head_zone(win.x(), win.y(), win.width(), win.height())
    lz = _zone_center(win)[2]
    cy = (sy0 + sy1) / 2
    assert cy < win.y() + lz[1]  # that spot is above the lying head's zone (sits in empty air)
    c.zigzag((sx0 + sx1) / 2, sy0 + 2, 1.5, amp=30)
    assert not win._pat_now


@needs_art
def test_one_way_sweep_over_lying_head_does_not_trigger(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    c = Clock(win, drv)
    cx, cy, z = _zone_center(win)
    for i in range(60):
        c.step(win.x() + z[0] - 40 + i * 6, cy)
    assert not win._pat_now


@needs_art
def test_petting_wakes_sleeper_and_blocks_dozing(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    lg = drv.lounge
    lg._to("sleep")
    for _ in range(90):
        drv.tick(1 / 30)
    assert lg.droop > 0.9
    c = Clock(win, drv)
    cx, cy, _ = _zone_center(win)
    c.zigzag(cx, cy, 1.5, amp=30)
    assert lg.state == "lounge_loop"  # woken, not asleep
    # keep petting longer than the sleep timer: no dozing, no yawn
    lg.t_lounge = L.SLEEP_AFTER_S - 1.0
    lg._next_yawn = 0.0
    for _ in range(4):
        c.zigzag(cx, cy, 1.0, amp=30)
    assert lg.state == "lounge_loop"


def test_lounge_state_machine_pat_timing():
    lg = L.Lounge(enabled=True, selfwalk=False)
    g = FieldGeom(0, 300, 800, 500)
    lg.on_drop(g, 400)
    for _ in range(120):
        lg.tick(1 / 30, g)
    assert lg.state == "lounge_loop"
    lg.set_petting(True)
    for _ in range(6):  # 0.2 s: ears twitch, eyes still open
        lg.tick(1 / 30, g)
    assert lg.droop < 0.05
    for _ in range(45):
        lg.tick(1 / 30, g)
    assert lg.droop > 0.9
    lg.set_petting(False)
    for _ in range(90):
        lg.tick(1 / 30, g)
    assert lg.droop < 0.05


def test_art_flick_starts_with_pat_and_tail_speeds_up(tmp_path):
    if not loungeart.available():
        pytest.skip("no art")
    art = loungeart.LoungeArt()
    art.set_pose(1.0, 0.0, 0.0)
    art.start_flick()
    assert art.frame_index("base") >= art.nb
    a = loungeart.LoungeArt()
    b = loungeart.LoungeArt()
    b.pat = 1.0
    for _ in range(30):
        a.step(1 / 30)
        b.step(1 / 30)
    assert b.phase > a.phase * 1.8


# ---- looser lying rule ----
def test_lying_params_derive_from_the_level():
    mid, low, high = petting.PARAMS["mid"], petting.PARAMS["low"], petting.PARAMS["high"]
    m = petting.lying_params("mid")
    assert (m.reversals, m.window_s, m.lenient) == (2, 2.2, True)
    assert m.min_swing == pytest.approx(mid.min_swing * 0.6) and m.min_speed == pytest.approx(mid.min_speed * 0.6)
    assert petting.lying_params("low").reversals == 3 and petting.lying_params("high").reversals == 2
    assert petting.lying_params("low").min_swing > m.min_swing > petting.lying_params("high").min_swing
    assert petting.lying_params("mid", {"mid": {"min_swing": 40}}).min_swing == pytest.approx(24.0)  # overrides feed in


def _run(det, pts, dt=1 / 30, t0=0.0):
    t, on = t0, False
    for x, y in pts:
        t += dt
        on = det.feed(t, x, y, True) or on
    return on


def _wiggle(n, ax, ay, hz, cx=0.0, cy=0.0):
    return [(cx + ax * math.sin(2 * math.pi * hz * i / 30), cy + ay * math.sin(2 * math.pi * hz * i / 30)) for i in range(n)]


def test_lying_detector_triggers_on_slow_small_diagonal_wiggles():
    det = petting.LyingPettingDetector("mid")
    assert _run(det, _wiggle(90, 14, 14, 1.7))  # diagonal, ~93 px/s legs of 28 px
    st = petting.PettingDetector("mid")
    assert not _run(st, _wiggle(90, 14, 14, 1.7))  # the standing rule would not have fired
    det = petting.LyingPettingDetector("mid")
    assert _run(det, _wiggle(90, 0, 16, 1.7))  # purely vertical strokes count too
    det = petting.LyingPettingDetector("mid")
    assert _run(det, _wiggle(90, 18, 0, 1.6))  # short horizontal strokes


def test_lying_detector_ignores_sweeps_parking_and_drift():
    det = petting.LyingPettingDetector("mid")
    assert not _run(det, [(i * 6.0, 0.0) for i in range(90)])  # one straight sweep
    det.reset()
    assert not _run(det, [(100.0, 50.0)] * 200)  # parked
    det.reset()
    assert not _run(det, [(100.0 + 0.6 * i, 50.0 + 0.2 * i) for i in range(200)])  # slow drift
    det.reset()
    assert not _run(det, _wiggle(120, 2.0, 2.0, 3.0))  # tiny tremor
    det.reset()
    assert not _run(det, [(0.0, 0.0)] * 30 + [(200.0, 0.0)] * 30)  # a jump and then stillness


def test_lying_detector_needs_two_reversals_in_window():
    det = petting.LyingPettingDetector("mid")
    pts = [(i * 4.0, 0.0) for i in range(12)] + [(48.0 - i * 4.0, 0.0) for i in range(12)]  # one fold only
    assert not _run(det, pts)
    pts2 = pts + [(i * 4.0, 0.0) for i in range(12)]
    det.reset()
    assert _run(det, pts2)


@needs_art
def test_lying_slow_diagonal_triggers_in_window_and_level_applies(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    c = Clock(win, drv)
    cx, cy, _ = _zone_center(win)
    for i in range(90):
        c.step(cx + 14 * math.sin(2 * math.pi * 1.7 * i / 30), cy + 14 * math.sin(2 * math.pi * 1.7 * i / 30))
    assert win._pat_now
    # sensitivity menu applies to the lying rule as well
    win.set_petting_level("low", persist=False)
    assert win._pat_det_lie.params == petting.lying_params("low")
    win.set_petting_level("high", persist=False)
    assert win._pat_det_lie.params == petting.lying_params("high")


@needs_art
def test_lying_zone_reaches_ears_and_chin_area(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    z = win._pet.lounge_head_zone(win.width(), win.height())
    k = win.height() / 940.0
    ledge = win.height() * (1 - loungeart.FOOT_PAD) + 0.008 * win.height()
    left = (win.width() - 640 * k) / 2
    top = ledge - 656 * k
    for fx, fy in ((140, 120), (560, 120), (330, 60), (330, 400), (150, 300)):  # ear tips, hair top, chin, cheek
        assert z[0] <= left + fx * k <= z[2] and z[1] <= top + fy * k <= z[3], (fx, fy)
    assert not (z[1] <= top + 520 * k <= z[3])  # forearms / lower body are outside


@needs_art
def test_calibration_log_records_lying_pat(qapp, tmp_path):
    import json
    win, drv = _lie(tmp_path)
    win.set_calibration_log(True, persist=False)
    c = Clock(win, drv)
    cx, cy, _ = _zone_center(win)
    for i in range(90):
        c.step(cx + 20 * math.sin(2 * math.pi * 2.0 * i / 30), cy)
    rows = [json.loads(x) for x in (win._calib.path).read_text().splitlines()]
    lying = [r for r in rows if r.get("lying") is True]
    kinds = {r["kind"] for r in lying}
    assert {"pat_fold", "pat_trigger"} <= kinds
    assert all("title" not in r for r in rows)
