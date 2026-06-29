import pytest
from fastapi.testclient import TestClient
from virtual_py.api.server import app, get_vm_provider
from virtual_py.core.interfaces import VMProvider
from virtual_py.core.models import VMInfo, VMStatus
from virtual_py.core.exceptions import VMNotFoundError

class MockProvider(VMProvider):
    async def create_vm(self, name, cpu_count, memory_mb, disk_path, network_name=None, iso_path=None, cloud_init=None, **kwargs):
        return True
    async def start_vm(self, name):
        if name == "missing": raise VMNotFoundError("missing")
        return True
    async def stop_vm(self, name, force=False):
        if name == "missing": raise VMNotFoundError("missing")
        return True
    async def delete_vm(self, name):
        if name == "missing": raise VMNotFoundError("missing")
        return True
    async def get_vm_info(self, name):
        if name == "missing": raise VMNotFoundError("missing")
        return VMInfo(name=name, status=VMStatus.RUNNING, cpu_count=2, memory_mb=2048, ip_address="10.0.0.1")
    async def list_vms(self):
        return [VMInfo(name="testvm", status=VMStatus.STOPPED, cpu_count=1, memory_mb=1024)]
    async def create_checkpoint(self, vm_name, checkpoint_name): return True
    async def restore_checkpoint(self, vm_name, checkpoint_name): return True
    async def delete_checkpoint(self, vm_name, checkpoint_name): return True
    async def list_checkpoints(self, vm_name): return ["snap1"]
    async def execute_command(self, vm_name, command, username=None, password=None): return "output"
    async def copy_file_to_guest(self, vm_name, host_path, guest_path, username=None, password=None): return True
    async def set_vm_memory(self, vm_name, memory_mb, live=False): return True
    async def set_vm_cpus(self, vm_name, cpu_count, live=False): return True
    async def attach_disk(self, vm_name, disk_path, controller_type=None): return True
    async def detach_disk(self, vm_name, disk_path): return True
    async def add_network_adapter(self, vm_name, switch_name): return "mac"
    async def remove_network_adapter(self, vm_name, adapter_mac): return True
    
    # Advanced
    async def enable_secure_boot(self, vm_name, enabled): return True
    async def enable_nested_virtualization(self, vm_name, enabled): return True
    async def enable_tpm(self, vm_name, enabled): return True
    async def create_network(self, name, subnet_cidr): return True
    async def delete_network(self, name): return True
    async def list_networks(self): return ["net1"]
    async def get_vm_metrics(self, vm_name): 
        from virtual_py.core.models import VMMetrics
        return VMMetrics(cpu_usage_percent=10.5, memory_demand_mb=512, uptime_seconds=100)
    async def migrate_vm(self, vm_name, target_host, **kwargs):
        if vm_name == "missing": raise VMNotFoundError("missing")
        return True
    async def clone_vm(self, vm_name, clone_name): return True
    async def export_vm(self, vm_name, export_path): return True
    async def create_storage_pool(self, name, path): return True
    async def delete_storage_pool(self, name): return True
    async def list_storage_pools(self): return ["pool1"]
    async def list_snapshots(self, vm_name): return ["snap1"]
    async def get_console_display(self, vm_name): return "snap1"
    async def attach_gpu(self, vm_name, mode="shared", **kwargs): return True
    async def detect_host_gpus(self): return [{"gpu": "Mock GPU", "vendor_id": "0x0000", "device_id": "0x0000", "vram_mb": "4096", "pci_address": "0000:01:00.0"}]
    async def restore_vm(self, vm_name, backup_path): return True

app.dependency_overrides[get_vm_provider] = lambda: MockProvider()
client = TestClient(app)

def test_list_vms():
    response = client.get("/vms")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "testvm"

def test_get_vm_info():
    response = client.get("/vms/testvm")
    assert response.status_code == 200
    assert response.json()["name"] == "testvm"

def test_get_missing_vm():
    response = client.get("/vms/missing")
    assert response.status_code == 404

def test_create_vm():
    response = client.post("/vms", json={
        "name": "newvm",
        "cpu_count": 4,
        "memory_mb": 4096,
        "disk_path": "/path/to/disk.vhdx"
    })
    assert response.status_code == 200

def test_metrics():
    response = client.get("/vms/testvm/metrics")
    assert response.status_code == 200
    assert response.json()["cpu_usage_percent"] == 10.5

def test_networks():
    res1 = client.get("/networks")
    assert res1.status_code == 200
    assert res1.json() == ["net1"]
    
    res2 = client.post("/networks/net2", json={"cidr": "10.0.0.0/24"})
    assert res2.status_code == 200

def test_api_migrate():
    response = client.post("/vms/testvm/migrate", json={"target_host": "192.168.1.50"})
    assert response.status_code == 200
    assert response.json()["message"] == "VM 'testvm' successfully migrated to '192.168.1.50'"

    response_missing = client.post("/vms/missing/migrate", json={"target_host": "192.168.1.50"})
    assert response_missing.status_code == 404

def test_api_checkpoints():
    res = client.get("/vms/testvm/checkpoints")
    assert res.status_code == 200
    assert res.json() == ["snap1"]

    res = client.post("/vms/testvm/checkpoints", json={"name": "newsnap"})
    assert res.status_code == 200

    res = client.post("/vms/testvm/checkpoints/newsnap/restore")
    assert res.status_code == 200

    res = client.delete("/vms/testvm/checkpoints/newsnap")
    assert res.status_code == 200

def test_api_guest_ops():
    res = client.post("/vms/testvm/execute", json={"command": "whoami"})
    assert res.status_code == 200
    assert res.json()["output"] == "output"

    res = client.post("/vms/testvm/copy-to-guest", json={
        "guest_path": "/tmp/test.txt",
        "file_content_b64": "SGVsbG8="
    })
    assert res.status_code == 200

def test_api_devices():
    res = client.post("/vms/testvm/disks", json={"disk_path": "/fake/disk"})
    assert res.status_code == 200

    res = client.request("DELETE", "/vms/testvm/disks", json={"disk_path": "/fake/disk"})
    assert res.status_code == 200

    res = client.post("/vms/testvm/network-adapters", json={"switch_name": "switch1"})
    assert res.status_code == 200
    assert res.json()["mac_address"] == "mac"

    res = client.delete("/vms/testvm/network-adapters/mac")
    assert res.status_code == 200

def test_api_console_display():
    res = client.get("/vms/testvm/console-display")
    assert res.status_code == 200
    assert res.json() == "snap1"

def test_api_backup():
    from unittest.mock import patch
    with patch("virtual_py.utils.backup.create_backup") as mock_backup:
        def side_effect(vm_name, path):
            with open(path, "wb") as f:
                f.write(b"dummybackup")
        mock_backup.side_effect = side_effect
        
        res = client.get("/vms/testvm/backup")
        assert res.status_code == 200
        assert res.content == b"dummybackup"

def test_api_gpu():
    res = client.post("/vms/testvm/gpu", json={"mode": "shared"})
    assert res.status_code == 200

def test_api_system_gpus():
    res = client.get("/system/gpus")
    assert res.status_code == 200
    assert len(res.json()) > 0
    assert res.json()[0]["gpu"] == "Mock GPU"

def test_api_restore():
    from io import BytesIO
    res = client.post("/vms/testvm/restore", files={"file": ("backup.tar.gz", BytesIO(b"dummydata"), "application/gzip")})
    assert res.status_code == 200



