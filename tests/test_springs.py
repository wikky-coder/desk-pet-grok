from desk_pet_grok.springs import SKIRT, Chain, Spring


def test_spring_settles_without_input():
    s = Spring(2.6, 0.5, 4.5)
    s.x = 3.0
    for _ in range(120):
        s.step(1 / 30)
    assert s.at_rest(0.02)


def test_spring_limit_and_accel_response():
    s = Spring(*SKIRT)
    for _ in range(30):
        s.step(1 / 30, 3000.0)
    assert -SKIRT[2] - 1e-9 <= s.x <= SKIRT[2] + 1e-9 and s.x < 0  # lags opposite to acceleration
    assert abs(s.x) > 1.0


def test_static_is_still():
    s = Spring(*SKIRT)
    for _ in range(100):
        s.step(1 / 30, 0.0)
    assert s.x == 0.0 and s.v == 0.0


def test_chain_travels_to_tip():
    c = Chain(6, (1.6, 0.45, 15, 0.8), (1.1, 0.3, 22, 1.2))
    for _ in range(10):
        c.step(1 / 30, 1500.0)
    x = [l.x for l in c.links]
    assert all(abs(v) > 0 for v in x)
