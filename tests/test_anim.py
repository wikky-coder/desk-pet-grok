"""Procedural animation unit tests (no Qt required)."""

from __future__ import annotations

from desk_pet_grok.anim import ProceduralAnim


def test_breath_oscillates() -> None:
    anim = ProceduralAnim()
    scales = []
    for _ in range(40):
        anim.tick(0.05)
        scales.append(anim.transform().scale_y)
    assert min(scales) < 1.0
    assert max(scales) > 1.0
    assert all(0.9 < s < 1.1 for s in scales)


def test_idle_no_walk_layers() -> None:
    anim = ProceduralAnim()
    anim.set_moving(False, 0.0)
    for _ in range(20):
        anim.tick(0.05)
        tf = anim.transform()
        assert tf.use_layers is False
        assert abs(tf.offset_x) < 0.01


def test_walk_uses_layers_not_whole_body_rock() -> None:
    """Moving without walk frames should use two-layer offsets, not big rotation."""
    anim = ProceduralAnim(prefer_layers=True)
    anim.set_walk_frames_active(False)
    anim.set_moving(True, 65.0, facing=1)
    saw_layers = False
    saw_stride = False
    max_abs_rot = 0.0
    for _ in range(40):
        anim.tick(0.025)
        tf = anim.transform()
        if tf.use_layers:
            saw_layers = True
            if abs(tf.lower_ox) > 0.5 or abs(tf.lower_oy) > 0.5:
                saw_stride = True
            max_abs_rot = max(max_abs_rot, abs(tf.rotation_deg))
    assert saw_layers
    assert saw_stride
    # Whole-sprite rotation should stay near zero (lean is upper_rot only)
    assert max_abs_rot < 0.5


def test_walk_frames_active_keeps_breath_only() -> None:
    anim = ProceduralAnim()
    anim.set_walk_frames_active(True)
    anim.set_moving(True, 65.0)
    for _ in range(20):
        anim.tick(0.03)
        tf = anim.transform()
        assert tf.use_layers is False
        assert abs(tf.rotation_deg) < 0.01


def test_jump_impulse_then_settles() -> None:
    anim = ProceduralAnim(jump_duration=0.28, jump_px=14.0)
    anim.trigger_jump()
    assert anim.jumping()
    ys = []
    t = 0.0
    while t < 0.4:
        anim.tick(0.02)
        ys.append(anim.transform().offset_y)
        t += 0.02
    assert min(ys) < -5.0
    assert not anim.jumping()
    assert abs(anim.transform().offset_y) < 5.0
