"""Window behaviours that read the cursor / drive pet features: eye-follow, head-pat, lounge, part-rig switches.

Mixed into ``PetWindow`` (see window.py); relies on the host's ``_pet``, ``_settings``, ``_lounge`` ... attributes."""

from __future__ import annotations

import datetime as _dt
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from desk_pet_grok import cling, config, greeting, holidays, powersave, eyefx, petting, puppet, shake, workalong

PAT_SAY_COOLDOWN_S = 20.0


class InteractionMixin:
    @property
    def look_at_mouse(self) -> bool:
        return self._look_at_mouse

    def set_look_at_mouse(self, enabled: bool, *, persist: bool = True) -> None:
        self._look_at_mouse = bool(enabled)
        if self._puppet and hasattr(self._pet, "set_gaze_enabled"):
            self._pet.set_gaze_enabled(self._look_at_mouse)  # type: ignore[union-attr]
        if persist:
            self._settings["look_at_mouse"] = self._look_at_mouse
            config.save_settings({"look_at_mouse": self._look_at_mouse})

    # ---- v4-6 work along (props from the front app's NAME) ----
    @property
    def work_along(self) -> bool:
        return bool(self._work.enabled)

    def set_work_along(self, enabled: bool, *, persist: bool = True) -> None:
        self._work.enabled = bool(enabled)
        if enabled:
            self._ensure_work_poller().start()
        else:
            if self._work_poller is not None:
                self._work_poller.stop()
            self._work.mode = None
            if self._puppet and hasattr(self._pet, "set_work"):
                self._pet.set_work(None)  # type: ignore[union-attr]
        if persist:
            self._settings["work_along"] = bool(enabled)
            config.save_settings({"work_along": bool(enabled)})

    def _ensure_work_poller(self):
        if self._work_poller is None:
            from desk_pet_grok import screen_mac

            self._work_poller = workalong.FrontPoller(screen_mac.front_app_name)
        return self._work_poller

    def _work_block_reason(self, dragging: bool = False) -> str:
        pet = self._pet
        if dragging:
            return "正在被拖动"
        if not self.isVisible():
            return "已隐藏"
        if self._cling.active:
            return "正扒着屏幕边"
        if self._anger.stage > 0:
            return "在生气"
        if hasattr(pet, "lounging") and pet.lounging():
            return "趴着（趴着不出道具）"
        if self._sm.quiet:
            return "安静模式"
        return ""

    def _work_blocked(self, dragging: bool) -> bool:
        return bool(self._work_block_reason(dragging))

    def work_status(self) -> str:
        """One line for the menu / settings: what front app was read and what she decided (for diagnosing)."""
        w = self._work
        if not w.enabled:
            return ""
        p = self._work_poller
        if p is None or not p._thread or not p._thread.is_alive():
            return "还没开始读前台软件（稍等几秒）"
        name = p.name
        mode = workalong.classify(name)
        label = {"read": "翻书", "code": "敲键盘", "terminal": "小终端", "draw": "画板"}
        txt = f"前台软件：{name or '没读到'} → " + (label[mode] if mode else "不出道具")
        why = self._work_block_reason()
        if why:
            txt += f"；现在不出：{why}"
        elif mode and w.mode == mode:
            txt += "；已出现"
        elif mode:
            txt += "；稳定 3 秒后出现（切换间隔 ≥25 秒）"
        return txt

    def _work_tick(self, dt: float, dragging: bool) -> None:
        w = self._work
        if not (w.enabled or w.mode) or not self._puppet or not hasattr(self._pet, "set_work"):
            return
        if w.enabled and self._work_poller is None:
            self._ensure_work_poller().start()
        name = self._work_poller.name if self._work_poller is not None else None
        ev = w.feed(time.monotonic(), dt, name, self._work_blocked(dragging))
        if ev is not None:
            self._pet.set_work(w.mode)  # type: ignore[union-attr]
            if ev[0] in ("enter", "switch"):
                self.lounge_say.emit("work_" + ev[1])

    # ---- v4-4 time-of-day greetings / festival decorations ----
    @property
    def time_greeting(self) -> bool:
        return bool(self._settings.get("time_greeting", True))

    def set_time_greeting(self, enabled: bool) -> None:
        self._settings["time_greeting"] = bool(enabled)
        config.save_settings({"time_greeting": bool(enabled)})

    @property
    def holiday_outfit(self) -> bool:
        return bool(self._settings.get("holiday_outfit", True))

    def set_holiday_outfit(self, enabled: bool) -> None:
        self._settings["holiday_outfit"] = bool(enabled)
        config.save_settings({"holiday_outfit": bool(enabled)})
        self._holiday_refresh(force=True)

    def _holiday_refresh(self, force: bool = False, today=None) -> None:
        if not self._puppet or not hasattr(self._pet, "set_holiday"):
            return
        key = holidays.festival_on(today or _dt.date.today()) if self.holiday_outfit else None
        self._pet.set_holiday(key)  # type: ignore[union-attr]

    def _greet_tick(self, dt: float, now_dt=None, cursor=None) -> None:
        """Every ~5 s: refresh the festival decoration (date roll-over) and greet once per period when the user is around."""
        g = self.__dict__.setdefault("_greet_state", {"acc": 0.0, "age": 0.0, "last_seen": 0.0, "cur": None, "idle": 0.0, "hol": None})
        g["acc"] += dt
        g["age"] += dt
        if g["acc"] < 5.0:
            return
        step, g["acc"] = g["acc"], 0.0
        now_dt = now_dt or _dt.datetime.now()
        self._holiday_refresh(today=now_dt.date())
        if not self.time_greeting or not self._puppet or not hasattr(self._pet, "greet"):
            return
        cur = cursor if cursor is not None else (QCursor.pos().x(), QCursor.pos().y())
        moved = g["cur"] is None or abs(cur[0] - g["cur"][0]) + abs(cur[1] - g["cur"][1]) >= 12
        g["cur"] = cur
        g["idle"] = 0.0 if moved else g["idle"] + step
        if g["age"] < 8.0 or g["idle"] > 120.0 or not self.isVisible() or self._sm.quiet or self._anger.stage > 0:
            return
        gr = self.__dict__.setdefault("_greeter", greeting.Greeter(self._settings.get("greeted")))
        period = gr.due(now_dt)
        if period is None:
            return
        gr.mark(period, now_dt)
        self._settings["greeted"] = dict(gr.seen)
        config.save_settings({"greeted": dict(gr.seen)})
        face, hop, icon = greeting.ACTION[period]
        self._pet.greet(icon, face)  # type: ignore[union-attr]
        if hop and hasattr(self._pet, "lounging") and not self._pet.lounging() and hasattr(self, "play_jump"):
            try:
                self.play_jump()
            except Exception:
                pass
        fest = holidays.festival_on(now_dt.date()) if self.holiday_outfit else None
        if fest and self._settings.get("holiday_greeted") != now_dt.date().isoformat():
            self._settings["holiday_greeted"] = now_dt.date().isoformat()
            config.save_settings({"holiday_greeted": now_dt.date().isoformat()})
            self.lounge_say.emit("festival_" + fest)
        else:
            self.lounge_say.emit("greet_" + period)

    # ---- v4-5 power saving ----
    @property
    def power_save(self) -> bool:
        return self._power.enabled

    def set_power_save(self, enabled: bool, persist: bool = True) -> None:
        self._power.enabled = bool(enabled)
        self._power_tick(0.0, True)
        if persist:
            self._settings["power_save"] = bool(enabled)
            config.save_settings({"power_save": bool(enabled)})

    def _power_tick(self, dt: float, dragging: bool, cursor=None, buttons: bool = None) -> None:
        """Called every motion tick with the real elapsed time (a slow tick must not count as activity or as a long idle)."""
        pw = self._power
        if not pw.enabled and pw.interval == powersave.NORMAL_MS:
            return
        cur = cursor if cursor is not None else (QCursor.pos().x(), QCursor.pos().y())
        down = buttons if buttons is not None else (QApplication.mouseButtons() != Qt.MouseButton.NoButton)
        last = getattr(self, "_power_last", None)
        pos = (self.x(), self.y())
        moved = last is None or abs(cur[0] - last[0][0]) + abs(cur[1] - last[0][1]) >= 4 or pos != last[1]
        self._power_last = (cur, pos)
        chat_open = False
        try:
            chat_open = bool(getattr(self, "chat_busy_fn", None) and self.chat_busy_fn())
        except Exception:
            pass
        active = bool(moved or down or dragging or self._pat_now or self._anger.stage > 0 or self._cling.peek or chat_open
                      or (self._puppet and hasattr(self._pet, "work_mode") and self._pet.work_mode() is not None))
        new = pw.feed(dt, active)
        if new is not None:
            self._motion_timer.setInterval(new)

    # ---- v4-3 cling to the screen border ----
    @property
    def cling_edge(self) -> bool:
        return bool(self._cling.enabled)

    def set_cling_edge(self, enabled: bool, *, persist: bool = True) -> None:
        self._cling.enabled = bool(enabled)
        if not enabled:
            self._cling_cancel()
        if persist:
            self._settings["cling_edge"] = bool(enabled)
            config.save_settings({"cling_edge": bool(enabled)})

    def _cling_rects(self):
        from PySide6.QtGui import QGuiApplication

        cur = self.screen()
        geo = (cur or QGuiApplication.primaryScreen()).geometry()
        mine = (float(geo.x()), float(geo.y()), float(geo.width()), float(geo.height()))
        others = [(float(s.geometry().x()), float(s.geometry().y()), float(s.geometry().width()), float(s.geometry().height()))
                  for s in QGuiApplication.screens() if s.geometry() != geo]
        return mine, others

    def _cling_side_now(self) -> int:
        if not (self._puppet and self._cling.enabled):
            return 0
        mine, others = self._cling_rects()
        return cling.attach_side((float(self.x()), float(self.y()), float(self.width()), float(self.height())), mine, others)

    def _cling_try(self, side: int | None = None) -> bool:
        """Called after a drop that did not become a lounge: at the far left / right of the screen she clings."""
        if not (self._puppet and self._cling.enabled and hasattr(self._pet, "set_cling")):
            return False
        if side is None:
            side = self._cling_side_now()
        if not side:
            return False
        self._cling.attach(side)
        self._pet.set_cling(side, False)  # type: ignore[union-attr]
        if self._pet.cling_side() != side:  # type: ignore[union-attr]
            self._cling.cancel()  # no art
            return False
        self._cling_said_peek = False
        self.lounge_say.emit("cling_on")
        return True

    def _cling_cancel(self) -> None:
        was = self._cling.active
        self._cling.cancel()
        if self._puppet and hasattr(self._pet, "set_cling"):
            self._pet.set_cling(0, False)  # type: ignore[union-attr]
        if was:
            self.lounge_say.emit("cling_off")

    def _cling_tick(self, dt: float) -> bool:
        """True while she clings (the caller then skips walking / lounging)."""
        if not self._cling.active:
            return False
        c = self._cling
        mine, _others = self._cling_rects()
        win = (float(self.x()), float(self.y()), float(self.width()), float(self.height()))
        cx = self._pet.cling_cut_x(float(self.height()))  # type: ignore[union-attr]
        if cx is None:
            self._cling_cancel()
            return False
        tx = cling.window_x(c.side, mine, cx)
        step = cling.SLIDE_PX_S * dt
        nx = self.x() + max(-step, min(step, tx - self.x()))
        if abs(nx - self.x()) >= 0.5:
            self.move(int(round(nx)), self.y())
        cur = QCursor.pos()
        c.tick(dt, cling.wants_peek(c.side, (float(cur.x()), float(cur.y())), mine, win, c.peek))
        self._pet.set_cling(c.side, c.peek)  # type: ignore[union-attr]
        if c.peek and not self._cling_said_peek:
            self._cling_said_peek = True
            self.lounge_say.emit("cling_peek")
        elif not c.peek:
            self._cling_said_peek = False
        return True

    # ---- v4-2 shake anger ----
    @property
    def shake_anger(self) -> bool:
        return bool(self._anger.enabled)

    def set_shake_anger(self, enabled: bool, *, persist: bool = True) -> None:
        self._anger.enabled = bool(enabled)
        if not enabled:
            self._anger.calm()
            self._anger.drain()
            if self._puppet and hasattr(self._pet, "set_anger"):
                self._pet.set_anger(0)  # type: ignore[union-attr]
        if persist:
            self._settings["shake_anger"] = bool(enabled)
            config.save_settings({"shake_anger": bool(enabled)})

    def _anger_tick(self, dt: float) -> None:
        if not self._puppet or not hasattr(self._pet, "set_anger"):
            return
        a = self._anger
        if not a.enabled and not a.stage:
            return
        now = time.monotonic()
        a.pat(bool(self._pat_now), dt)
        a.tick(now, dt)
        for ev in a.drain():
            if ev[0] == "stage":
                self._pet.set_anger(ev[1])  # type: ignore[union-attr]
                if ev[1] in shake.LINE and ev[1] > ev[2]:  # escalation only; stage 0 (faded out) is followed by a 'calm' event
                    self.lounge_say.emit(shake.LINE[ev[1]])
            elif ev[0] == "soothe":  # petting moved her one step calmer (sulk -> fuming -> puffed): face + a still-grumpy line
                self._pet.set_anger(ev[1])  # type: ignore[union-attr]
                self.lounge_say.emit("anger_soothe")
            elif ev[0] == "calm":
                self._pet.set_anger(0)  # type: ignore[union-attr]
                if hasattr(self._pet, "greet"):
                    self._pet.greet("heart", "happy", hold=5.0)  # type: ignore[union-attr]
                self.lounge_say.emit(shake.CALM_LINE)
                self.mood_event("pat")

    # ---- F8 tail boost ----
    @property
    def tail_boost(self) -> bool:
        return bool(self._settings.get("tail_boost", True))

    def set_tail_boost(self, enabled: bool, *, persist: bool = True) -> None:
        self._settings["tail_boost"] = bool(enabled)
        if self._puppet and hasattr(self._pet, "set_tail_boost"):
            self._pet.set_tail_boost(bool(enabled))  # type: ignore[union-attr]
        if persist:
            config.save_settings({"tail_boost": bool(enabled)})

    # ---- F7 lying-pose variants ----
    @property
    def lounge_variants(self) -> bool:
        return bool(self._settings.get("lounge_variants", False))

    def set_lounge_variants(self, enabled: bool, *, persist: bool = True) -> None:
        self._settings["lounge_variants"] = bool(enabled)
        if self._puppet and hasattr(self._pet, "set_lounge_variants"):
            self._pet.set_lounge_variants(bool(enabled))  # type: ignore[union-attr]
        if persist:
            config.save_settings({"lounge_variants": bool(enabled)})

    # ---- F6 mood ----
    @property
    def mood_enabled(self) -> bool:
        return bool(self._mood.enabled)

    def set_mood_enabled(self, enabled: bool, *, persist: bool = True) -> None:
        self._mood.enabled = bool(enabled)
        if not enabled:
            self._mood.reset()
        if self._puppet and hasattr(self._pet, "set_mood_enabled"):
            self._pet.set_mood_enabled(bool(enabled))  # type: ignore[union-attr]
        if persist:
            self._settings["mood"] = bool(enabled)
            config.save_settings({"mood": bool(enabled)})

    def mood_event(self, kind: str) -> None:
        """pat / fall / poke / neglect / activity -> the mood machine (no-op while the switch is off)."""
        self._mood.event(kind)
        self._mood_apply()

    def _mood_on_say(self, category: str) -> None:
        if category == "pet_fall":
            self.mood_event("fall")

    def _mood_apply(self) -> None:
        if self._puppet and hasattr(self._pet, "set_mood"):
            self._pet.set_mood(self._mood.current())  # type: ignore[union-attr]

    def _mood_tick(self) -> None:
        if not self._mood.enabled:
            return
        now = time.monotonic()
        dt, self._mood_last = now - self._mood_last, now
        self._mood.tick(min(dt, 5.0), time.localtime().tm_hour)
        self._mood_apply()

    @property
    def calibration_log(self) -> bool:
        return bool(self._calib.enabled)

    def set_calibration_log(self, enabled: bool, *, persist: bool = True) -> None:
        """Advanced: record numeric gesture/edge data for threshold tuning (default off, see dbglog.py)."""
        self._calib.enabled = bool(enabled)
        if persist:
            self._settings["calibration_log"] = bool(enabled)
            config.save_settings({"calibration_log": bool(enabled)})

    @property
    def petting_enabled(self) -> bool:
        return self._petting_on

    def set_petting_enabled(self, enabled: bool, *, persist: bool = True) -> None:
        self._petting_on = bool(enabled)
        if not enabled:
            self._set_pat(False)
            self._pat_det.reset()
            self._pat_det_lie.reset()
        if persist:
            self._settings["petting"] = self._petting_on
            config.save_settings({"petting": self._petting_on})

    @property
    def petting_level(self) -> str:
        level = str(self._settings.get("petting_level", "mid"))
        return level if level in petting.LEVELS else "mid"

    def set_petting_level(self, level: str, *, persist: bool = True) -> None:
        level = level if level in petting.LEVELS else "mid"
        self._pat_det.set_level(level)
        self._pat_det_lie.set_level(level)
        if persist:
            self._settings["petting_level"] = level
            config.save_settings({"petting_level": level})
        else:
            self._settings["petting_level"] = level

    def _set_pat(self, on: bool) -> None:
        if on == self._pat_now:
            return
        self._pat_now = on
        if on:
            self.mood_event("pat")
        if self._puppet and hasattr(self._pet, "set_petting"):
            self._pet.set_petting(on)  # type: ignore[union-attr]
        self._lounge.lounge.set_petting(on)  # lying down: wakes her, no dozing/yawning meanwhile, eyes close happily

    def feed_cursor(self, now: float, cx: float, cy: float, *, dragging: bool = False, buttons_down: bool = False) -> bool:
        """Read-only use of the global cursor: eye gaze target + head-pat detection. Never touches events or focus.
        Returns whether she is currently being patted."""
        if self._puppet and hasattr(self._pet, "set_gaze"):
            ex = self.x() + 0.5 * (eyefx.EYES[0][0] + eyefx.EYES[1][0]) * self.height() / puppet.CANVAS_H
            ey = self.y() + eyefx.EYES[0][1] * self.height() / puppet.CANVAS_H
            gx, gy = eyefx.gaze_vector((cx, cy), (ex, ey)) if self._look_at_mouse else (0.0, 0.0)
            self._pet.set_gaze(gx, gy)  # type: ignore[union-attr]
        if not (self._puppet and self._petting_on) or dragging or buttons_down or self._drag_origin is not None:
            self._pat_det.reset()
            self._pat_det_lie.reset()
            self._set_pat(False)
            return False
        lz = self._pet.lounge_head_zone(float(self.width()), float(self.height())) if hasattr(self._pet, "lounge_head_zone") else None
        if lz is not None:  # lying pose: the head is somewhere else than when standing
            zone = (self.x() + lz[0], self.y() + lz[1], self.x() + lz[2], self.y() + lz[3])
        else:
            zone = petting.head_zone(float(self.x()), float(self.y()), float(self.width()), float(self.height()))
        angry = self._anger.stage > 0 and lz is None
        if angry:  # angry: a bigger head zone and the forgiving (lying) stroke rule, so petting her always registers
            x0, y0, x1, y1 = zone
            gx, gy = 0.2 * (x1 - x0), 0.25 * (y1 - y0)
            zone = (x0 - gx, y0 - gy, x1 + gx, y1 + gy)
            det = self._pat_det_anger
            self._pat_det.reset()
            self._pat_det_lie.reset()
        else:
            det = self._pat_det_lie if lz is not None else self._pat_det
            (self._pat_det if lz is not None else self._pat_det_lie).reset()
            self._pat_det_anger.reset()
        on = det.feed(now, cx, cy, petting.in_zone(zone, cx, cy))
        if on and not self._pat_now and now - self._pat_last_say >= PAT_SAY_COOLDOWN_S:
            self._pat_last_say = now
            self.lounge_say.emit("pet_head")
        self._set_pat(on)
        return on

    @property
    def lounge(self) -> bool:
        return bool(self._puppet and self._lounge.enabled)

    def set_lounge(self, enabled: bool, *, persist: bool = True) -> None:
        """Lounge on the top edge of the front window (needs the 2.5D pet + part rig assets)."""
        enabled = bool(enabled and self._puppet and self.part_rig_available())
        self._lounge.set_enabled(enabled)
        if persist:
            self._settings["lounge"] = enabled
            config.save_settings({"lounge": enabled})

    @property
    def lounge_ax(self) -> bool:
        return bool(self._settings.get("lounge_ax", False))

    def _apply_lounge_probe(self, ax_on: bool, *, prompt: bool) -> None:
        from desk_pet_grok import ax_probe, focus_probe

        edge = focus_probe.WindowEdgeProbe()
        if not ax_on:
            self._lounge.probe = edge
            return
        if prompt and not ax_probe.is_trusted():
            ax_probe.open_accessibility_settings()  # onboarding: user ticks the app; we keep the window-edge fallback
        self._lounge.probe = ax_probe.HybridProbe(ax_probe.AXProbe(), edge)

    def set_lounge_ax(self, enabled: bool, *, persist: bool = True) -> None:
        self._settings["lounge_ax"] = bool(enabled)
        self._apply_lounge_probe(bool(enabled), prompt=True)
        if persist:
            config.save_settings({"lounge_ax": bool(enabled)})

    @property
    def lounge_dock(self) -> bool:
        return bool(self._lounge.dock_enabled)

    def set_lounge_dock(self, enabled: bool, *, persist: bool = True) -> None:
        """Also lounge on the top edge of a bottom Dock (menu: 也趴程序坞)."""
        self._lounge.dock_enabled = bool(enabled)
        if persist:
            self._settings["lounge_dock"] = bool(enabled)
            config.save_settings({"lounge_dock": bool(enabled)})

    @property
    def lounge_selfwalk(self) -> bool:
        return bool(self._lounge.lounge.selfwalk)

    def set_lounge_selfwalk(self, enabled: bool, *, persist: bool = True) -> None:
        self._lounge.set_selfwalk(enabled)
        if persist:
            self._settings["lounge_selfwalk"] = bool(enabled)
            config.save_settings({"lounge_selfwalk": bool(enabled)})

    @property
    def part_rig(self) -> bool:
        return bool(self._puppet and getattr(self._pet, "part_rig_on", lambda: False)())

    @property
    def part_turn(self) -> bool:
        return bool(self._puppet and getattr(self._pet, "part_turn_on", lambda: False)())

    def set_part_turn(self, enabled: bool, *, persist: bool = True) -> None:
        if self._puppet:
            enabled = self._pet.set_part_turn(enabled)  # type: ignore[union-attr]
        else:
            enabled = False
        if persist:
            self._settings["part_turn"] = enabled
            config.save_settings({"part_turn": enabled})

    def part_rig_available(self) -> bool:
        from desk_pet_grok import partrig

        return bool(self._puppet and partrig.available())

    def set_part_rig(self, enabled: bool, *, persist: bool = True) -> None:
        if self._puppet:
            enabled = self._pet.set_part_rig(enabled)  # type: ignore[union-attr]
        else:
            enabled = False
        if persist:
            self._settings["part_rig"] = enabled
            config.save_settings({"part_rig": enabled})
