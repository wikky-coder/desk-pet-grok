"""F8 tail swing: natural driver, lying-pose tail layer (no ghost of the rest tail), rigs, switch."""
from __future__ import annotations

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_lounge_pet import _restore_cfg_env, needs_art, qapp  # noqa: E402,F401

from desk_pet_grok import config, loungeart  # noqa: E402
from desk_pet_grok.tailmotion import TailDriver  # noqa: E402


def _run(mode, secs=60, seed=3):
    d = TailDriver(random.Random(seed))
    return [d.step(1 / 60, **mode) for _ in range(int(secs * 60))]


def test_calm_swing_is_visible_but_bounded_and_never_a_plain_loop():
    xs = _run({})
    assert 8.0 <= max(xs) <= 19.5 and -19.5 <= min(xs) <= -8.0
    rms = (sum(x * x for x in xs) / len(xs)) ** 0.5
    assert 3.5 <= rms <= 9.0
    # not periodic: the second half does not repeat the first
    h = len(xs) // 2
    assert max(abs(a - b) for a, b in zip(xs[:h], xs[h:])) > 3.0
    # irregular quick wags: at least a few zero-crossing bursts faster than the slow sway
    fast = sum(1 for a, b in zip(xs, xs[1:]) if abs(b - a) > 0.6)
    assert fast > 20


def test_modes_ordering_pat_bigger_asleep_tiny():
    rms = lambda xs: (sum(x * x for x in xs) / len(xs)) ** 0.5  # noqa: E731
    calm, pat, asleep, happy = rms(_run({})), rms(_run({"pat": 1.0})), rms(_run({"asleep": 1.0})), rms(_run({"happy": 1.0}))
    assert pat > calm * 1.5
    assert asleep < 3.0 and asleep < calm * 0.5
    assert happy >= calm * 0.95


def test_different_seeds_differ_and_limit_holds():
    a, b = _run({}, seed=1), _run({}, seed=2)
    assert a != b
    assert all(abs(x) <= 19.0 + 1e-6 for x in a + b)


def test_default_on():
    assert config._DEFAULTS["tail_boost"] is True


@needs_art
def test_assets_have_tail_layers_except_curl():
    for n in ("side", "chin", "stretch"):
        a = loungeart.LoungeArt(loungeart.VARIANT_DIR / n)
        assert a.tail_layer() and a.runtime_breath
        lo, hi = a.tail_meta["limits"]
        assert lo <= -10 and hi >= 10
    b = loungeart.LoungeArt()
    assert b.tail_layer() and b.tail_meta["limits"][1] >= 15  # base: little room to the left, uses the whole free range
    assert not loungeart.LoungeArt(loungeart.VARIANT_DIR / "curl").tail_layer()  # tail wraps in front of the body: not separable


@needs_art
def test_tail_layer_replaces_rest_tail_no_ghost(qapp):
    from PySide6.QtGui import QColor, QImage, QPainter
    import numpy as np
    art = loungeart.LoungeArt(loungeart.VARIANT_DIR / "side")
    art.step = lambda dt: None
    H = 500; W = int(H * 0.7659)

    def img(deg):
        art.tail_deg = deg
        im = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied); im.fill(0)
        p = QPainter(im); art.paint(p, W, H, 1.0, 1.0, 0.0, 0.0); p.end()
        return np.frombuffer(im.constBits(), np.uint8).reshape(H, im.bytesPerLine() // 4, 4)[:, :W, 3].astype(int)
    a0, a1, a2 = img(0.0), img(-16.0), img(16.0)
    assert np.abs(a1 - a0).sum() > 3000 and np.abs(a2 - a0).sum() > 3000  # the tail really moves (obvious)
    # the rest-pose tail pixels (alpha at 0 deg) that are not covered at +-16 deg must be empty: no leftover rest tail
    k = H / 940.0; left = (W - art.fw * k) / 2
    bx, by, bw, bh = art.tail_meta["box"]
    top = H * (1 - loungeart.EDGE_UP) + loungeart.sink_px(H) + art.base_off * k - art.fh * k
    x0, x1, y0, y1 = int(left + bx * k) + 6, int(left + (bx + bw) * k) - 6, int(top + by * k) + 6, int(top + (by + bh) * k) - 6
    only_rest = (a0[y0:y1, x0:x1] > 200) & (a1[y0:y1, x0:x1] < 30)
    # tail pixels exist only where the new angle draws them: rest-only pixels belong to the part the tail left
    assert only_rest.sum() > 200


@needs_art
def test_switch_off_restores_gentle_sway_and_rigs_follow(qapp, tmp_path):
    from test_lounge_pet import _lie
    win, drv = _lie(tmp_path)
    win.set_tail_boost(False, persist=False)
    pet = win._pet
    assert pet.tail_boost() is False and pet._lounge_art.tail_on is False
    for _ in range(300):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert abs(pet._lounge_art.tail_deg) <= 5.01  # the old +-5 deg sway
    win.set_tail_boost(True, persist=False)
    assert pet._lounge_art.tail_on is True and pet._rig.tail_boost is True


def test_menu_and_settings_rows(qapp):
    from test_settings_panel import Model
    from desk_pet_grok.menu import build_pet_menu
    st = {"v": True}
    cb = Model().cb(); cb.is_tail_boost = lambda: st["v"]; cb.set_tail_boost = lambda v: st.update(v=v)
    menu = build_pet_menu(None, cb)
    acts = [a for a in menu.actions() if a.text() == "尾巴摆动增强"]
    assert len(acts) == 1 and acts[0].isChecked()
    acts[0].trigger()
    assert st["v"] is False
