"""Single-instance key naming."""

from desk_pet_grok.app import SINGLE_INSTANCE_KEY


def test_single_instance_key_name():
    assert SINGLE_INSTANCE_KEY == "desk-pet-grok"
