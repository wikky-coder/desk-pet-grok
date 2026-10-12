from desk_pet_grok.ax_probe import HybridProbe, is_editable_role
from desk_pet_grok.focus_probe import FakeProbe, FieldGeom

WIN = FieldGeom(0, 30, 1000, 700, "window")
FIELD = FieldGeom(100, 600, 500, 28, "field", "AXTextField")


def test_editable_roles_exclude_secure_fields():
    for r in ("AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"):
        assert is_editable_role(r)
    for r in ("AXSecureTextField", "AXButton", "", None):
        assert not is_editable_role(r)


def test_hybrid_uses_field_when_trusted_and_field_found():
    h = HybridProbe(FakeProbe([FIELD]), FakeProbe([WIN]), trusted=lambda: True)
    assert h.sample() == FIELD


def test_hybrid_falls_back_without_permission_and_never_calls_ax():
    class Boom:
        def sample(self):
            raise AssertionError("AX must not be queried without permission")

    h = HybridProbe(Boom(), FakeProbe([WIN]), trusted=lambda: False)
    assert h.sample() == WIN
    assert h.permission_missing is True


def test_hybrid_falls_back_when_no_field_or_ax_errors():
    h = HybridProbe(FakeProbe([None]), FakeProbe([WIN]), trusted=lambda: True)
    assert h.sample() == WIN

    class Err:
        def sample(self):
            raise RuntimeError("x")

    assert HybridProbe(Err(), FakeProbe([WIN]), trusted=lambda: True).sample() == WIN


def test_trust_is_rechecked_with_a_slow_interval():
    calls = []
    now = [0.0]

    def trusted():
        calls.append(1)
        return True

    h = HybridProbe(FakeProbe([FIELD]), FakeProbe([WIN]), trusted=trusted, recheck_s=10.0, clock=lambda: now[0])
    for _ in range(5):
        h.sample()
    assert len(calls) == 1
    now[0] = 11.0
    h.sample()
    assert len(calls) == 2
