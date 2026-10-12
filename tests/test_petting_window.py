"""Window-level head-pat + passive eye-follow (synthetic cursor trajectories; no real mouse)."""

from __future__ import annotations

import math
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from PySide6.QtWidgets import QApplication

from desk_pet_grok import eyefx, petting
from desk_pet_grok.menu import PetMenuCallbacks, build_pet_menu
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def mkwin(qapp, **settings):
    base = {"puppet25d": True, "motion_mode": "wander"}
    base.update(settings)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.resize(220, 287)
    w.move(400, 300)
    w.show()
    qapp.processEvents()
    assert w._pet.size() == w.size()
    return w


def head_center(w):
    z = petting.head_zone(w.x(), w.y(), w.width(), w.height())
    return (z[0] + z[2]) / 2, (z[1] + z[3]) / 2


def stroke(w, cycles=3.5, amp=40.0, period=0.4, dt=1 / 30.0, t0=0.0, cy=None, **kw):
    cx, hy = head_center(w)
    out = []
    for i in range(int(cycles * period / dt)):
        t = t0 + i * dt
        out.append(w.feed_cursor(t, cx + amp * math.sin(2 * math.pi * (t - t0) / period), hy if cy is None else cy, **kw))
    return out


def test_stroking_head_triggers_reaction_and_one_line(qapp):
    w = mkwin(qapp)
    said = []
    w.lounge_say.connect(said.append)
    flags = stroke(w)
    assert any(flags) and w._pet.petting()
    assert said == ["pet_head"]
    stroke(w, t0=2.0)  # second stroke within 20 s: reaction but no new line
    assert said == ["pet_head"]


def test_say_cooldown_expires(qapp):
    w = mkwin(qapp)
    said = []
    w.lounge_say.connect(said.append)
    stroke(w)
    w.feed_cursor(5.0, 0.0, 0.0)  # leaves: reaction ends
    assert not w._pet.petting() or w._pet._pat_on is False
    stroke(w, t0=25.0)
    assert said == ["pet_head", "pet_head"]


def test_straight_sweep_and_parked_cursor_do_not_trigger(qapp):
    w = mkwin(qapp)
    cx, hy = head_center(w)
    for i in range(40):
        assert not w.feed_cursor(i / 30.0, cx - 100 + i * 5.0, hy)
    for i in range(60):
        assert not w.feed_cursor(2 + i / 30.0, cx, hy)


def test_disabled_does_nothing(qapp):
    w = mkwin(qapp, petting=False)
    assert not any(stroke(w))


def test_no_reaction_while_dragging_or_button_down(qapp):
    w = mkwin(qapp)
    assert not any(stroke(w, dragging=True))
    assert not any(stroke(w, buttons_down=True, t0=3.0))


def test_reaction_releases_after_leaving(qapp):
    w = mkwin(qapp)
    stroke(w)
    assert w._pat_now
    w.feed_cursor(3.0, 5.0, 5.0)
    assert not w._pat_now


def test_sensitivity_menu_setting(qapp):
    w = mkwin(qapp)
    w.set_petting_level("high", persist=False)
    assert w.petting_level == "high" and w._pat_det.params == petting.params_for("high")
    w.set_petting_level("nonsense", persist=False)
    assert w.petting_level == "mid"


def test_pet_pose_changes_picture_and_rig_amount(qapp):
    w = mkwin(qapp)
    pet = w._pet
    for _ in range(3):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    pet.grab()
    before = pet._buf.copy()
    pet.set_petting(True)
    for _ in range(60):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    pet.grab()
    time.sleep(0.3)  # let the rig<->sheet cross-fade (wall clock) finish
    pet.grab()
    assert pet.pat_amount() > 0.95
    assert bytes(pet._buf.constBits()) != bytes(before.constBits())
    pet.set_petting(False)
    for _ in range(120):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.pat_amount() < 0.01


def test_petting_while_lounging_keeps_loaf_pose(qapp):
    w = mkwin(qapp, part_rig=True, lounge=True)
    if not w.part_rig_available():
        pytest.skip("rig assets missing")
    pet = w._pet
    pet.set_lounge((1.0, 0.0, 0.0))
    pet.set_petting(True)
    for _ in range(30):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    pet.grab()
    assert pet.lounging() and pet.pat_amount() > 0.5
    assert pet._buf is not None


# ---- passive eye-follow ----------------------------------------------------------------------------------------------
def test_gaze_vector_geometry():
    assert eyefx.gaze_vector((100, 100), (100, 100)) == (0.0, 0.0)
    gx, gy = eyefx.gaze_vector((1000, 100), (100, 100))
    assert gx == pytest.approx(1.0) and abs(gy) < 1e-9
    gx, gy = eyefx.gaze_vector((100, -300), (100, 100))
    assert gy == pytest.approx(-1.0)
    gx, gy = eyefx.gaze_vector((130, 100), (100, 100))
    assert 0 < gx < 0.2  # near the pet: gentle


def test_cursor_moves_eyes_only_not_body(qapp):
    w = mkwin(qapp)
    w._motion_timer.stop()  # the wander timer would move her on its own between the two snapshots (racy)
    pet = w._pet
    for _ in range(90):  # let any leftover turn progress settle first
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    before = (w.x(), w.y(), w.motion_mode, pet.logic.s.tp, pet.logic.want_facing)
    w.feed_cursor(0.0, w.x() - 500.0, w.y() + 100.0)
    for _ in range(40):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    gx, gy = pet.gaze()
    assert gx < -0.8
    assert (w.x(), w.y(), w.motion_mode, pet.logic.s.tp, pet.logic.want_facing) == before
    w.feed_cursor(1.0, w.x() + 800.0, w.y() + 100.0)
    for _ in range(40):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.gaze()[0] > 0.8


def test_gaze_shifts_pixels_only_in_the_eye_region(qapp):
    w = mkwin(qapp)
    pet = w._pet
    pet._idle_idx = lambda: 5  # freeze the idle animation so only the gaze can change pixels
    pet._flick_at = 1e18
    for _ in range(3):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    pet.grab()
    a = pet._buf.copy()
    pet.set_gaze(-1.0, 0.0)
    for _ in range(40):
        pet.drive(1 / 30.0, want_walk=False, facing=1, look=False, dragging=False)
    pet.grab()
    b = pet._buf
    k = 287 / 470.0
    mir = pet.logic.mirror()
    eyes = [((220.0 / k - ex) if mir else ex, ey) for ex, ey in eyefx.EYES]
    diff_outside = diff_inside = 0
    for y in range(0, b.height(), 2):
        for x in range(0, b.width(), 2):
            if a.pixel(x, y) != b.pixel(x, y):
                inside = any(abs(x - ex * k) < 26 * k and abs(y - ey * k) < 22 * k for ex, ey in eyes)
                diff_inside += inside
                diff_outside += not inside
    assert diff_inside > 5 and diff_outside <= 3


def test_gaze_can_be_turned_off(qapp):
    w = mkwin(qapp, look_at_mouse=False)
    assert not w.look_at_mouse
    w.feed_cursor(0.0, w.x() - 500.0, w.y())
    assert w._pet.gaze() == (0.0, 0.0) and w._pet._gaze_t == (0.0, 0.0)
    w.set_look_at_mouse(True, persist=False)
    w.feed_cursor(0.0, w.x() - 500.0, w.y())
    assert w._pet._gaze_t[0] < -0.5


def test_legacy_follow_mode_migrates(qapp):
    w = mkwin(qapp, motion_mode="follow")
    assert w.motion_mode.value == "still" and w.look_at_mouse
    w.set_motion_mode("follow", persist=False)
    assert w.motion_mode.value == "still"


def _cb(**kw):
    return PetMenuCallbacks(
        get_height=lambda: 220, set_height=lambda h: None, is_quiet=lambda: False, set_quiet=lambda q: None,
        is_penetrate=lambda: False, set_penetrate=lambda p: None, is_always_on_top=lambda: True,
        set_always_on_top=lambda v: None, is_bubble_visible=lambda: True, set_bubble_visible=lambda v: None,
        get_motion_mode=lambda: "wander", set_motion_mode=lambda m: None, set_api_key=lambda: None,
        clear_chat=lambda: None, say_line=lambda: None, show_weather=lambda: None, show_about=lambda: None,
        is_autostart=lambda: False, set_autostart=lambda e: None, quit_app=lambda: None, **kw)


def test_menu_has_toggles_and_no_follow_mode(qapp):
    levels, flags = [], []
    m = build_pet_menu(None, _cb(set_petting_level=levels.append, set_petting=flags.append,
                                get_petting_level=lambda: "high"))
    titles = [a.text() for a in m.actions()]
    assert "眼睛看向鼠标" in titles and "摸头" in titles
    mode = next(a for a in m.actions() if a.text() == "模式").menu()
    assert [a.text() for a in mode.actions()] == ["散步", "原地"]
    pat = next(a for a in m.actions() if a.text() == "摸头").menu()
    acts = [a for a in pat.actions() if a.text().startswith("灵敏度")]
    assert [a.isChecked() for a in acts] == [False, False, True]
    acts[0].trigger()
    assert levels == ["low"]
    next(a for a in pat.actions() if a.isCheckable() and "开启" in a.text()).trigger()
    assert flags == [False]


def _eye_img(squint, h=470):
    from PySide6.QtGui import QImage, QPainter, QColor, QTransform
    k = h / 470.0
    img = QImage(int(360 * k), h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 243, 228))
    p = QPainter(img)
    p.setBrush(QColor(200, 120, 40))  # fake iris
    for ex, ey in eyefx.EYES:
        p.drawEllipse(int((ex - 14) * k), int((ey - 14) * k), int(28 * k), int(28 * k))
    p.end()
    eyefx.apply(img, QTransform(), k, 1.0, squint=squint)
    return img


def test_happy_eye_closes_smoothly_and_erases_iris(qapp):
    def iris(img, k=1.0):
        ex, ey = eyefx.EYES[0]
        return sum(1 for y in range(int((ey - 16) * k), int((ey + 16) * k)) for x in range(int((ex - 20) * k), int((ex + 20) * k))
                   if img.pixelColor(x, y).red() > 180 and img.pixelColor(x, y).blue() < 90)
    counts = [iris(_eye_img(s)) for s in (0.0, 0.3, 0.6, 1.0)]
    assert counts[0] > 300 and counts[-1] == 0 and counts == sorted(counts, reverse=True)
    assert iris(_eye_img(1.0, 160), 160 / 470.0) == 0


def test_happy_eye_stays_in_eye_region_and_has_lash_line(qapp):
    a, b = _eye_img(0.0), _eye_img(1.0)
    k = 1.0
    out = dark = 0
    for y in range(0, a.height(), 2):
        for x in range(0, a.width(), 2):
            if a.pixel(x, y) != b.pixel(x, y):
                near = any(abs(x - ex) < 34 and abs(y - ey) < 32 for ex, ey in eyefx.EYES)
                out += not near
    assert out == 0
    ex, ey = eyefx.EYES[0]
    assert any(b.pixelColor(int(ex) + dx, int(ey) + dy).lightness() < 140 for dx in range(-8, 9) for dy in range(-20, 6))


def _real_eye_img(squint):
    import os
    from PySide6.QtGui import QImage, QTransform
    sheet = QImage(os.path.join(os.path.dirname(eyefx.__file__), "..", "assets", "sprites25d", "idle_front.png"))
    f = sheet.copy(0, 0, 360, 470).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    eyefx.apply(f, QTransform(), 1.0, 1.0, squint=squint)
    return f


def _dark_runs(img, x, y0, y1, thr=130):
    rows = [y for y in range(y0, y1) if img.pixelColor(x, y).lightness() < thr]
    runs = []
    for y in rows:
        if runs and y - runs[-1][-1] <= 3:  # the stroke has a white sheen: merge across it
            runs[-1].append(y)
        else:
            runs.append([y])
    return [r for r in runs if len(r) >= 3]  # ignore 1-2 px hair-line specks


def test_closed_eye_plate_asset_present_and_sized(qapp):
    plates = eyefx._load_plates()
    assert len(plates) == 2 and plates[0].width() == 68 and plates[0].height() == 60


def test_closed_eye_is_one_smiling_stroke_and_nothing_else_dark(qapp):
    """Fully closed: the old lash / crease / white / iris are replaced by the reference smiling eye: exactly one dark
    run per eye column, no stray dark clusters in the eye box (old lash tail etc. only allowed on the face outline)."""
    b = _real_eye_img(1.0)
    for ex, ey in eyefx.EYES:
        for dx in (-8, 0, 8):
            runs = _dark_runs(b, int(ex) + dx, int(ey - 34), int(ey + 18))
            assert len(runs) == 1 and len(runs[0]) <= 16, (dx, runs)
        dark_rows = {y for y in range(int(ey - 30), int(ey + 16))
                     if sum(1 for x in range(int(ex - 21), int(ex + 21)) if b.pixelColor(x, y).lightness() < 110) >= 3}
        assert max(dark_rows) - min(dark_rows) <= 18  # one band, not a lash above and a line below


def test_closed_eye_mirrored_world_flips_plates(qapp):
    from PySide6.QtGui import QImage, QPainter, QTransform
    f = _real_eye_img(0.0)
    img = QImage(360, 470, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.translate(360, 0)
    p.scale(-1, 1)
    p.drawImage(0, 0, f)
    p.end()
    tr = QTransform()
    tr.translate(360, 0)
    tr.scale(-1, 1)
    eyefx.apply(img, tr, 1.0, 1.0, squint=1.0)
    for ex, ey in eyefx.EYES:
        assert len(_dark_runs(img, int(360 - ex), int(ey - 34), int(ey + 18))) == 1


def test_open_eye_untouched_and_midway_has_no_double_lash(qapp):
    a, o = _real_eye_img(0.0), _real_eye_img(0.0)
    assert a == o
    m = _real_eye_img(0.75)  # old lash must already be gone while new lines fade in: far fewer dark px than open
    ex, ey = eyefx.EYES[0]
    def dk(img):
        return sum(1 for y in range(int(ey - 30), int(ey + 16)) for x in range(int(ex - 30), int(ex + 30)) if img.pixelColor(x, y).lightness() < 110)
    assert dk(m) < dk(a)


def test_closed_eye_is_an_upward_arch_without_highlight(qapp):
    b = _real_eye_img(1.0)
    for ex, ey in eyefx.EYES:
        def mid(dx):
            rows = [y for y in range(int(ey - 34), int(ey + 18)) if b.pixelColor(int(ex) + dx, y).lightness() < 130]
            assert rows and rows[-1] - rows[0] + 1 == len(rows), (dx, rows)  # contiguous: no white sheen dot inside
            return (rows[0] + rows[-1]) / 2.0
        centre, left, right = mid(0), mid(-12), mid(12)
        assert centre < left - 3 and centre < right - 3  # apex clearly above both ends (smile arch ^)


def test_half_closed_has_no_big_iris(qapp):
    """At 50% the lids are essentially shut: only a sliver of iris colour may remain."""
    m = _real_eye_img(0.5)
    ex, ey = eyefx.EYES[0]
    iris = sum(1 for y in range(int(ey - 20), int(ey + 20)) for x in range(int(ex - 22), int(ex + 22))
               if (lambda c: c.red() > 200 and c.blue() < 120 and c.green() < 190)(m.pixelColor(x, y)))
    assert iris < 25, iris
