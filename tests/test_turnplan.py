from desk_pet_grok import turnplan as t


def test_endpoints_are_pure_key_views():
    p0 = t.plan(0.0)
    assert p0["trunk"][0] == (0, 1.0) and all(o == 0.0 for _, o in p0["trunk"][1:]) and p0["tail"] == [(0, 1.0)]
    assert p0["head"][0][0] <= 1  # head already leads into the arms-down front key
    assert t.plan(1.0) == {p: [(len(t.KEYS) - 1, 1.0)] for p in ("head", "trunk", "tail")}


def test_head_leads_trunk_leads_tail_and_yaw_is_monotonic():
    prev = {p: -1.0 for p in t.LEAD}
    for i in range(0, 101):
        tp = i / 100
        y = {p: t.part_yaw(p, tp) for p in t.LEAD}
        assert y["head"] >= y["trunk"] - 1e-9 >= y["tail"] - 2e-9
        for p in y:
            assert y[p] >= prev[p] - 1e-9
            prev[p] = y[p]


def test_at_most_two_views_and_tail_never_double():
    for i in range(0, 101):
        pl = t.plan(i / 100)
        assert all(1 <= len(v) <= 2 for v in pl.values())
        assert len(pl["tail"]) == 1 or abs(pl["tail"][1][1]) < 1.0  # tail swaps (near) hard


def test_head_swaps_hard_so_hairpin_is_never_doubled():
    for i in range(0, 101):
        pl = t.plan(i / 100)["head"]
        yaw = t.part_yaw("head", i / 100)
        if len(pl) == 2:  # only inside the 0.01 deg hard-swap band
            mid = 0.5 * (t.KEYS[pl[0][0]] + t.KEYS[pl[1][0]])
            assert abs(yaw - mid) <= 0.01 + 1e-9


def test_xform_registers_neighbour_views_to_same_extent_at_swap():
    ext = [[100.0, 400.0], [150.0, 350.0], [200.0, 300.0]]
    tc, sx0, sc0 = t.xform(ext, 11.0, 0)
    _, sx1, sc1 = t.xform(ext, 11.0, 1)
    # both neighbours map their extent onto the same target width/centre
    assert abs((ext[0][1] - ext[0][0]) * sx0 - (ext[1][1] - ext[1][0]) * sx1) < 1e-6
    assert abs(tc - 250.0) < 60
