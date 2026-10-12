"""Bubble / chat card stay inside the pet's screen (edges, corners, Dock, multi-screen), flip sides, tail points at her."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from desk_pet_grok import placement as P
from desk_pet_grok.placement import place_box

SCR = (0.0, 25.0, 1440.0, 800.0)  # menu bar on top, Dock at the bottom already excluded
PET = (263, 220)


def inside(pl, size, scr=SCR, inset=0.0):
    return (pl.x >= scr[0] - inset - 1e-6 and pl.y >= scr[1] - inset - 1e-6
            and pl.x + size[0] <= scr[0] + scr[2] + inset + 1e-6 and pl.y + size[1] <= scr[1] + scr[3] + inset + 1e-6)


@pytest.mark.parametrize("ax,ay", [(600, 300), (0, 25), (1440 - 263, 25), (0, 825 - 220), (1440 - 263, 825 - 220),
                                   (600, 25), (600, 825 - 220), (0, 400), (1440 - 263, 400)])
def test_box_always_inside_screen(ax, ay):
    size = (280, 120)
    pl = place_box((ax, ay, *PET), size, [SCR])
    assert inside(pl, size)


def test_prefers_above_then_flips_below_at_top():
    size = (280, 120)
    mid = place_box((600, 400, *PET), size, [SCR])
    assert mid.side == "above" and mid.y + size[1] <= 400 and mid.tail_edge == "bottom"
    top = place_box((600, 25, *PET), size, [SCR])  # lying at the very top of the screen
    assert top.side == "below" and top.y >= 25 + PET[1] and top.tail_edge == "top"


def test_flips_beside_when_neither_above_nor_below_fits():
    scr = (0.0, 0.0, 1000.0, 300.0)
    size = (260, 200)
    pl = place_box((400, 40, *PET), size, [scr])
    assert pl.side in ("right", "left") and inside(pl, size, scr)
    assert pl.tail_edge == ("left" if pl.side == "right" else "right")


def test_horizontal_clamp_and_tail_still_points_at_her():
    size = (280, 100)
    pl = place_box((0, 400, *PET), size, [SCR])  # pet at the left edge
    assert pl.x >= 0
    assert 0 <= pl.tail_pos <= size[0] and pl.x + pl.tail_pos == pytest.approx(PET[0] / 2)
    pr = place_box((1440 - 263, 400, *PET), size, [SCR])
    assert pr.x + size[0] <= 1440 and pr.x + pr.tail_pos == pytest.approx(1440 - 263 / 2)


def test_dock_bottom_lounging_goes_above():
    # lying on the Dock top: window bottom == available bottom
    pl = place_box((600, 825 - 220, *PET), (280, 100), [SCR])
    assert pl.side == "above"


def test_multi_screen_uses_the_pets_screen():
    left = (-1920.0, 0.0, 1920.0, 1080.0)
    right = (0.0, 25.0, 1440.0, 800.0)
    above = (200.0, -900.0, 1600.0, 900.0)  # a monitor stacked above
    size = (280, 120)
    pl = place_box((-300, 500, *PET), size, [left, right, above])
    assert pl.screen == left and inside(pl, size, left)
    pl = place_box((-1900, 5, *PET), size, [left, right])  # top-left corner of the left screen
    assert inside(pl, size, left) and pl.side == "below"
    # pet straddling two screens: the larger overlap wins
    assert P.pick_screen((-250, 300, 263, 220), [left, right]) == left  # 250 px of her on the left screen
    assert P.pick_screen((-100, 300, 263, 220), [left, right]) == right  # 163 px on the right one
    assert P.pick_screen((-10, 300, 263, 220), [left, right]) == right
    # off every screen: nearest
    assert P.pick_screen((5000, 300, 263, 220), [left, right]) == right


def test_stacked_screen_above_does_not_pull_the_box_there():
    top_screen = (0.0, -1000.0, 1440.0, 1000.0)
    main = (0.0, 25.0, 1440.0, 800.0)
    pl = place_box((600, 25, *PET), (280, 100), [top_screen, main])
    assert pl.screen == main and pl.y >= 25  # she is on the main screen: below, not on the monitor above


def test_inset_lets_only_shadow_overhang():
    pl = place_box((0, 400, *PET), (300, 100), [SCR], inset=7.0)
    assert pl.x >= -7.0 - 1e-6


def test_tall_box_bigger_than_screen_is_clamped_not_lost():
    pl = place_box((600, 300, *PET), (300, 2000), [SCR])
    assert pl.y >= SCR[1] - 1e-6


# ---- widgets ----
@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _anchor(x, y):
    w = QWidget()
    w.setGeometry(x, y, *PET)
    return w


def _screens(monkeypatch, rects):
    import desk_pet_grok.bubble as B
    monkeypatch.setattr(B, "screen_rects", lambda: rects)


@pytest.mark.parametrize("ax,ay", [(600, 300), (0, 25), (1440 - 263, 25), (0, 605), (1440 - 263, 605), (600, 25), (600, 605)])
def test_bubble_inside_screen_with_tail_pointing_at_pet(qapp, monkeypatch, ax, ay):
    from desk_pet_grok.bubble import BubbleWidget, _SHADOW
    _screens(monkeypatch, [SCR])
    b = BubbleWidget()
    a = _anchor(ax, ay)
    b.show_text("今天也要加油喵。" * 6)
    b.reposition_above(a)
    g = b.geometry()
    assert g.left() >= SCR[0] - _SHADOW and g.top() >= SCR[1] - _SHADOW
    assert g.right() <= SCR[0] + SCR[2] + _SHADOW and g.bottom() <= SCR[1] + SCR[3] + _SHADOW
    # the tail tip lies on the axis through her centre and its edge faces her
    ag = a.frameGeometry()
    if b._tail_edge in ("top", "bottom"):
        assert b._tail_pos + g.x() == pytest.approx(ag.x() + ag.width() / 2, abs=1.5)
        assert (b._tail_edge == "bottom") == (g.bottom() <= ag.top() + 10)
    else:
        assert b._tail_pos + g.y() == pytest.approx(ag.y() + ag.height() / 2, abs=1.5)


def test_bubble_regrows_and_stays_on_screen(qapp, monkeypatch):
    from desk_pet_grok.bubble import BubbleWidget, _SHADOW
    _screens(monkeypatch, [SCR])
    b = BubbleWidget()
    a = _anchor(600, 25)  # at the top: bubble below her; long streaming text must not run off the bottom
    b.show_text("短喵。")
    b.reposition_above(a)
    for i in range(30):
        b.append_text("很长很长的一句话喵。")
        assert b.geometry().bottom() <= SCR[1] + SCR[3] + _SHADOW
        assert b.geometry().top() >= SCR[1] - _SHADOW
    assert b._tail_edge == "top"


def test_bubble_flips_when_she_moves_to_the_top(qapp, monkeypatch):
    from desk_pet_grok.bubble import BubbleWidget
    _screens(monkeypatch, [SCR])
    b = BubbleWidget()
    a = _anchor(600, 400)
    b.show_text("你好喵。")
    b.reposition_above(a)
    assert b._tail_edge == "bottom" and b.geometry().bottom() <= 400
    a.move(600, 25)
    b.reposition_above(a)
    assert b._tail_edge == "top" and b.geometry().top() >= 25 + PET[1] - 12


def test_bubble_keeps_focus_flags(qapp):
    from desk_pet_grok.bubble import BubbleWidget
    b = BubbleWidget()
    f = b.windowFlags()
    assert f & Qt.WindowType.WindowDoesNotAcceptFocus and f & Qt.WindowType.WindowStaysOnTopHint


def test_panel_inside_screen_and_reclamps_when_it_grows(qapp, monkeypatch):
    from desk_pet_grok.chat_panel import ChatPanel, _MARGIN
    _screens(monkeypatch, [SCR])
    p = ChatPanel()
    a = _anchor(0, 25)
    p.show()
    p.reposition_above(a)
    g = p.geometry()
    assert g.left() >= SCR[0] - _MARGIN and g.top() >= SCR[1] - _MARGIN and g.bottom() <= SCR[1] + SCR[3] + _MARGIN
    a.move(600, 400)
    p.reposition_above(a)
    assert p.geometry().bottom() <= 400 + 10 and p.geometry().top() >= SCR[1] - _MARGIN
    p._mine_bubble.setText("很长的一句话" * 20)
    p._mine_bubble.setFixedWidth(220)
    p._mine_bubble.show()
    p._relayout()
    g = p.geometry()
    assert g.top() >= SCR[1] - _MARGIN and g.bottom() <= SCR[1] + SCR[3] + _MARGIN
    assert g.left() >= SCR[0] - _MARGIN and g.right() <= SCR[0] + SCR[2] + _MARGIN
    # nothing changed about focus behaviour
    assert p.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_panel_flips_below_at_screen_top(qapp, monkeypatch):
    from desk_pet_grok.chat_panel import ChatPanel
    _screens(monkeypatch, [SCR])
    p = ChatPanel()
    p.show()
    a = _anchor(600, 25)
    p.reposition_above(a)
    assert p._side in ("below", "right", "left")
    if p._side == "below":
        assert p.geometry().top() >= 25 + PET[1] - 30
