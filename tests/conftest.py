import pytest


@pytest.fixture(autouse=True)
def _restore_puppet_globals():
    """Pet25D overwrites puppet.STRIDE_PX_PER_FRAME from the manifest; keep tests independent."""
    from desk_pet_grok import puppet

    saved = puppet.STRIDE_PX_PER_FRAME
    yield
    puppet.STRIDE_PX_PER_FRAME = saved
