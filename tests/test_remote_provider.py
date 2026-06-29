import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from virtual_py.providers.remote.provider import RemoteProvider
from virtual_py.core.models import VMInfo, VMStatus
from virtual_py.core.exceptions import VMException

@pytest.fixture
def remote_provider():
    provider = RemoteProvider(base_url="http://localhost:8080")
    # Replace the internal client with a mock
    provider.client = MagicMock(spec=httpx.AsyncClient)
    provider.client.request = AsyncMock()
    return provider

@pytest.mark.asyncio
async def test_remote_create_vm(remote_provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": "created"}
    remote_provider.client.request.return_value = mock_response

    res = await remote_provider.create_vm(
        name="testvm", cpu_count=2, memory_mb=2048, disk_path="/dev/null"
    )
    assert res is True
    remote_provider.client.request.assert_called_once_with(
        "POST", "/vms", json={
            "name": "testvm",
            "cpu_count": 2,
            "memory_mb": 2048,
            "disk_path": "/dev/null",
            "network_name": None,
            "iso_path": None,
            "cloud_init": None,
            "raw_user_data": None,
            "sysprep": None
        }
    )

@pytest.mark.asyncio
async def test_remote_get_vm_info(remote_provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "testvm",
        "status": "running",
        "cpu_count": 4,
        "memory_mb": 4096,
        "ip_address": "10.0.0.1"
    }
    remote_provider.client.request.return_value = mock_response

    info = await remote_provider.get_vm_info("testvm")
    assert info.name == "testvm"
    assert info.status == VMStatus.RUNNING
    assert info.cpu_count == 4
    assert info.memory_mb == 4096
    assert info.ip_address == "10.0.0.1"

@pytest.mark.asyncio
async def test_remote_error_handling(remote_provider):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Error"
    remote_provider.client.request.return_value = mock_response

    with pytest.raises(VMException) as exc:
        await remote_provider.list_vms()
    assert "Remote API Error" in str(exc.value)

@pytest.mark.asyncio
async def test_remote_migrate(remote_provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": "migrated"}
    remote_provider.client.request.return_value = mock_response

    res = await remote_provider.migrate_vm("testvm", "10.0.0.99")
    assert res is True
    remote_provider.client.request.assert_called_once_with(
        "POST", "/vms/testvm/migrate", json={"target_host": "10.0.0.99"}
    )
