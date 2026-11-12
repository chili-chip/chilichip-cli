import pathlib

import pytest


@pytest.fixture
def test_resources(request):
    # Get path to "test_relocs" resource dir
    return pathlib.Path(request.module.__file__).parent / 'resources'


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    """Keep the Chili Platform token in a temporary folder and never sleep between polls."""
    from chilichip import platform_api
    monkeypatch.setattr(platform_api, 'config_dir', lambda: tmp_path / 'config')
    monkeypatch.setattr(platform_api, 'cache_dir', lambda: tmp_path / 'cache')
    monkeypatch.setattr(platform_api.time, 'sleep', lambda seconds: None)
    monkeypatch.delenv('CHILICHIP_PLATFORM_URL', raising=False)
    return tmp_path
