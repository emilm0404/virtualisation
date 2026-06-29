import pytest
from virtual_py.catalog import default_registry, OSTemplate

def test_catalog_registry_loads_templates():
    templates = default_registry.list_all()
    assert len(templates) > 0, "Catalog should have predefined templates loaded"
    
    # check that specific OS templates exist
    alpine = default_registry.get("alpine-3.20")
    assert alpine is not None
    assert isinstance(alpine, OSTemplate)
    assert alpine.min_memory_mb == 256
    assert alpine.cloud_init_supported is True
    
    ubuntu = default_registry.get("ubuntu-24.04")
    assert ubuntu is not None
    assert ubuntu.default_username == "ubuntu"
    
    win = default_registry.get("win11-eval")
    assert win is not None
    assert win.cloud_init_supported is False

@pytest.mark.asyncio
async def test_downloader_mock():
    # just checking that the module imports correctly since we don't want to actually download big ISOs in CI.
    from virtual_py.catalog.downloader import download_iso_async
    assert callable(download_iso_async)
