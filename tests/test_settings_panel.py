"""F3: settings panel stays in sync with the menu callbacks, shows explicit permission hints, never takes focus."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desk_pet_grok import onboarding
from desk_pet_grok.menu import PetMenuCallbacks, build_pet_menu
from desk_pet_grok.settings_panel import SettingsPanel, ax_note, build_sections


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Model:
    """Fake app state behind the callbacks (stands in for PetWindow)."""

    def __init__(self):
        self.v = dict(height=220, quiet=False, pen=False, top=True, bub=True, mode="wander", look=True, pat=True,
                      lvl="mid", rig=True, turn=False, lounge=True, dock=True, walk=True, ax=False, calib=False)
        self.trusted = False

    def cb(self) -> PetMenuCallbacks:
        v = self.v

        def g(k):
            return lambda: v[k]

        def s(k):
            return lambda x: v.__setitem__(k, x)

        return PetMenuCallbacks(
            get_height=g("height"), set_height=s("height"), is_quiet=g("quiet"), set_quiet=s("quiet"),
            is_penetrate=g("pen"), set_penetrate=s("pen"), is_always_on_top=g("top"), set_always_on_top=s("top"),
            is_bubble_visible=g("bub"), set_bubble_visible=s("bub"), get_motion_mode=g("mode"), set_motion_mode=s("mode"),
            set_api_key=lambda: None, clear_chat=lambda: None, say_line=lambda: None, show_weather=lambda: None,
            show_about=lambda: None, is_autostart=lambda: False, set_autostart=lambda e: None, quit_app=lambda: None,
            is_part_rig=g("rig"), set_part_rig=s("rig"), part_rig_available=lambda: True, is_part_turn=g("turn"),
            set_part_turn=s("turn"), is_lounge=g("lounge"), set_lounge=s("lounge"), is_lounge_dock=g("dock"),
            set_lounge_dock=s("dock"), is_lounge_selfwalk=g("walk"), set_lounge_selfwalk=s("walk"),
            is_lounge_ax=g("ax"), set_lounge_ax=s("ax"), is_look_at_mouse=g("look"), set_look_at_mouse=s("look"),
            is_petting=g("pat"), set_petting=s("pat"), get_petting_level=g("lvl"), set_petting_level=s("lvl"),
            is_calibration_log=g("calib"), set_calibration_log=s("calib"),
        )


def _panel(m):
    return SettingsPanel(build_sections(m.cb(), ax_trusted=lambda: m.trusted, open_ax=lambda: m.v.__setitem__("opened", True)))


def _menu_checked(menu, label_part):
    for a in menu.actions():
        if label_part in a.text():
            return a.isChecked()
    for a in menu.actions():
        if a.menu():
            r = _menu_checked(a.menu(), label_part)
            if r is not None:
                return r
    return None


def test_panel_edit_reaches_menu(qapp):
    m = Model()
    p = _panel(m)
    p.checkbox_for("摸头反应").setChecked(False)
    assert m.v["pat"] is False
    assert _menu_checked(build_pet_menu(None, m.cb()), "开启摸头反应") is False


def test_menu_change_refreshes_panel(qapp):
    m = Model()
    p = _panel(m)
    assert p.checkbox_for("眼睛看向鼠标").isChecked()
    m.v["look"] = False  # changed from the right-click menu
    p.refresh()
    assert not p.checkbox_for("眼睛看向鼠标").isChecked()


def test_dependent_rows_disable(qapp):
    m = Model()
    p = _panel(m)
    assert p.checkbox_for("也趴程序坞").isEnabled()
    m.v["lounge"] = False
    p.refresh()
    assert not p.checkbox_for("也趴程序坞").isEnabled()
    assert not p.checkbox_for("精确到输入框").isEnabled()


def test_ax_hint_is_explicit_when_not_trusted(qapp):
    assert "未授权" in ax_note(True, False)
    assert "未授权" not in ax_note(True, True)
    m = Model()
    p = _panel(m)
    assert "未授权" not in p.note_for("精确到输入框")
    m.v["ax"] = True
    p.refresh()
    assert "未授权" in p.note_for("精确到输入框")
    m.trusted = True
    p.refresh()
    assert "未授权" not in p.note_for("精确到输入框")


def test_choice_row_updates_and_syncs(qapp):
    m = Model()
    p = _panel(m)
    rb = next(w for r, w in p._widgets if r.text == "摸头灵敏度")["choice"]
    dict(rb)["high"].setChecked(True)
    assert m.v["lvl"] == "high"
    m.v["lvl"] = "low"
    p.refresh()
    assert dict(rb)["low"].isChecked()


def test_panel_never_accepts_focus(qapp):
    p = _panel(Model())
    f = p.windowFlags()
    assert f & Qt.WindowType.WindowDoesNotAcceptFocus
    assert p.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert p.focusPolicy() == Qt.FocusPolicy.NoFocus
    for r, w in p._widgets:
        for c in ([w["check"]] if "check" in w else []) + [rb for _, rb in w.get("choice", [])]:
            assert c.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_menu_has_settings_entry_only_when_wired(qapp):
    m = Model()
    cb = m.cb()
    m1 = build_pet_menu(None, cb)
    assert not any("设置…" == a.text() for a in m1.actions())
    cb.open_settings = lambda: None
    m2 = build_pet_menu(None, cb)
    assert any("设置…" == a.text() for a in m2.actions())


def test_onboarding_only_on_fresh_install():
    assert onboarding.should_onboard({"window_x": None, "window_y": None})
    assert not onboarding.should_onboard({"window_x": 10, "window_y": 20})
    assert not onboarding.should_onboard({"onboarded": True, "window_x": None})


def test_onboarding_three_pages_and_done_once(qapp):
    done = []
    g = onboarding.OnboardingPanel(on_done=lambda: done.append(1))
    assert g.page == 0
    g.advance()
    g.advance()
    assert g.page == 2 and not done
    g.advance()
    g.close()
    assert done == [1]
    assert g.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus


def test_onboarding_skip(qapp):
    done = []
    g = onboarding.OnboardingPanel(on_done=lambda: done.append(1))
    g._skip.click()
    assert done == [1]
