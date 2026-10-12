"""Pure-logic tests for the 2.5D puppet (state machine, bounds, prefs, hit test)."""

from desk_pet_grok import puppet
from desk_pet_grok.puppet import PuppetLogic

DT = 1 / 30


def run(lg, secs, **kw):
    for _ in range(int(secs / DT)):
        lg.tick(DT, kw.get("dx", 0.0), kw.get("h", 220))


def test_clamp_height_and_size():
    assert puppet.clamp_height(50) == 160
    assert puppet.clamp_height(999) == 320
    assert puppet.clamp_height(220) == 220
    w, h = puppet.size_for_height(220)
    assert h == 220 and w == round(220 * 360 / 470)


def test_clamp_to_screen():
    r = (0, 25, 1440, 800)
    assert puppet.clamp_to_screen(-50, -50, 100, 200, r) == (0, 25)
    assert puppet.clamp_to_screen(5000, 5000, 100, 200, r) == (1340, 625)
    assert puppet.clamp_to_screen(10, 30, 100, 200, r) == (10, 30)


def test_hit_alpha():
    a = [[0] * 10 for _ in range(10)]
    a[5][5] = 255
    assert puppet.hit_alpha(a, 5, 5, pad=0)
    assert puppet.hit_alpha(a, 6, 6, pad=1)
    assert not puppet.hit_alpha(a, 0, 0, pad=2)
    assert not puppet.hit_alpha([], 0, 0)


def test_idle_to_walk_to_idle():
    lg = PuppetLogic(60, [15, 51])
    assert lg.s.clip() == "idle"
    lg.set_walk(True, 1)
    run(lg, 0.3)
    assert lg.s.clip() == "turn"  # turning, no instant cut
    assert not lg.walking
    run(lg, 1.0)
    assert lg.s.clip() == "walk" and lg.walking
    lg.set_walk(False, 1)
    run(lg, 3.0)
    assert lg.s.clip() == "idle"
    assert lg.s.walk_pos == 15.0


def test_walk_frame_follows_distance_not_time():
    lg = PuppetLogic(60, [15, 51])
    lg.set_walk(True, 1)
    run(lg, 1.5)
    p0 = lg.s.walk_pos
    run(lg, 1.0, dx=0.0)  # no ground movement → feet do not move
    assert lg.s.walk_pos == p0
    k = 220 / puppet.CANVAS_H
    lg.tick(DT, puppet.STRIDE_PX_PER_FRAME * k * 3, 220)
    assert abs(((lg.s.walk_pos - p0) % 60) - 3.0) < 1e-6


def test_facing_flip_turns_through_front():
    lg = PuppetLogic(60, [15, 51])
    lg.set_walk(True, 1)
    run(lg, 2.0)
    assert lg.s.clip() == "walk" and lg.s.side_facing == 1
    lg.set_walk(True, -1)
    run(lg, 1.5)
    assert lg.s.tp < 1.0  # leaving side after settling to a rest frame
    run(lg, 4.0)
    assert lg.s.side_facing == -1 and lg.s.clip() == "walk" and not lg.mirror()


def test_drag_stops_walk_immediately_and_leans():
    lg = PuppetLogic(60, [15, 51])
    lg.set_walk(True, 1)
    run(lg, 2.0)
    lg.set_dragging(True, 600.0)
    assert not lg.walking and lg.s.gain == 0.0
    run(lg, 0.5)
    assert lg.s.lean > 5.0 and lg.s.lean <= puppet.LEAN_MAX_DEG
    lg.set_dragging(False)
    run(lg, 3.0)
    assert lg.s.lean == 0.0
    lg.set_walk(True, 1)  # resumes from new position
    run(lg, 2.0)
    assert lg.walking


def test_hop_runs_and_ends():
    lg = PuppetLogic()
    lg.hop()
    run(lg, 0.2)
    y, sq = lg.hop_offset()
    assert y < 0
    run(lg, 0.5)
    assert lg.hop_offset() == (0.0, 1.0)


def test_look_partial_turn_only():
    lg = PuppetLogic()
    lg.want_facing = -1
    lg.set_look(True)
    run(lg, 2.0)
    assert abs(lg.s.tp - puppet.LOOK_TP) < 1e-6 and not lg.mirror()
    assert not lg.walking
    lg.set_look(False)
    run(lg, 2.0)
    assert lg.s.tp == 0.0


def test_freeze_when_quiet_and_wake():
    lg = PuppetLogic()
    run(lg, puppet.IDLE_FREEZE_S + 1)
    assert lg.s.frozen
    lg.hop()
    assert not lg.s.frozen


def test_walk_gain_speed_match():
    # 65 px/s at 220 px tall → frames/s = ground / (stride*k)
    k = 220 / puppet.CANVAS_H
    assert abs(puppet.walk_gain(65, 220) - 65 / (1.5 * k)) < 1e-9


def test_mirror_matches_direction_of_sprites_drawn_facing_left():
    """Shipped side sprites face LEFT: walking/looking right must flip, left must not."""
    assert puppet.NATIVE_FACING == -1
    for want, flip in ((1, True), (-1, False)):
        lg = PuppetLogic(60, [15])
        lg.want_facing = want
        lg.set_walk(True, want)
        run(lg, 2.0)
        assert lg.s.clip() == "walk" and lg.mirror() is flip
        lg2 = PuppetLogic()
        lg2.want_facing = want
        lg2.set_look(True)
        run(lg2, 2.0)
        assert lg2.mirror() is flip


def test_turn_waits_for_idle_phase_and_walk_starts_on_enter_frame():
    lg = PuppetLogic(60, [15])
    lg.phase_ok = False
    lg.set_walk(True, 1)
    run(lg, 1.0)
    assert lg.s.tp == 0.0
    lg.phase_ok = True
    run(lg, 2.0)
    assert lg.s.clip() == "walk" and int(lg.s.walk_pos) == 15


def test_turn_frame_eased_and_monotonic():
    lg = PuppetLogic()
    fr = []
    for tp in [i / 20 for i in range(21)]:
        lg.s.tp = tp
        fr.append(lg.turn_frame(27))
    assert fr == sorted(fr) and fr[0] == 0 and fr[-1] == 26
    assert fr[2] <= 1 and fr[18] >= 25  # slow in, slow out


def test_manifest_turn_matches_sheet():
    import json
    from pathlib import Path
    from PIL import Image
    root = Path(__file__).resolve().parents[1] / "assets" / "sprites25d"
    m = json.loads((root / "manifest.json").read_text())
    c = m["clips"]["turn_out"]
    rows = -(-c["frames"] // c["cols"])
    assert Image.open(root / c["sheet"]).size == (c["cols"] * c["fw"], rows * c["fh"])
    assert m["native_facing"] == -1 and m["walk_enter_frame"] in m["walk_rest_frames"]


def test_hop_table_matches_bible():
    lg = PuppetLogic()
    lg.hop()
    peak = 0.0
    seen_sx = []
    for _ in range(40):
        lg.tick(1 / 100)
        y, sx, sy = lg.hop_pose()
        peak = min(peak, y)
        seen_sx.append(sx * sy)
    assert abs(peak + 16.0) < 1.0
    assert all(0.97 <= v <= 1.03 for v in seen_sx)  # volume roughly conserved
    for _ in range(10):
        lg.tick(1 / 100)
    assert lg.hop_pose() == (0.0, 1.0, 1.0)


def test_drag_tilt_spring_overshoots_then_settles():
    lg = PuppetLogic()
    lg.set_dragging(True, 400.0)  # target 10 deg
    peak = 0.0
    for _ in range(90):
        lg.tick(1 / 30)
        peak = max(peak, lg.s.lean)
    assert peak > 10.0 and peak <= puppet.LEAN_MAX_DEG  # underdamped: overshoots, capped
    lg.set_dragging(False)
    for _ in range(150):
        lg.tick(1 / 30)
    assert lg.s.lean == 0.0
