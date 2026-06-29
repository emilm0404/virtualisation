import httpx
from typing import List, Optional
from virtual_py.core.interfaces import VMProvider
from virtual_py.core.models import VMInfo, VMStatus
from virtual_py.core.exceptions import VMException, VMNotFoundError

class RemoteProvider(VMProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def _request(self, method: str, path: str, **kwargs):
        try:
            response = await self.client.request(method, path, **kwargs)
            if response.status_code == 404:
                raise VMNotFoundError("Resource not found")
            if response.status_code >= 400:
                raise VMException(f"Remote API Error: {response.text}")
            return response.json()
        except httpx.RequestError as e:
            raise VMException(f"Network error connecting to {self.base_url}: {str(e)}")

    async def create_vm(self, name: str, cpu_count: int, memory_mb: int, disk_path: str, network_name: Optional[str] = None, iso_path: Optional[str] = None, cloud_init: Optional[dict] = None, raw_user_data: Optional[str] = None, sysprep: Optional[dict] = None, **kwargs) -> bool:
        payload = {
            "name": name,
            "cpu_count": cpu_count,
            "memory_mb": memory_mb,
            "disk_path": disk_path,
            "network_name": network_name,
            "iso_path": iso_path,
            "cloud_init": cloud_init,
            "raw_user_data": raw_user_data,
            "sysprep": sysprep
        }
        await self._request("POST", "/vms", json=payload)
        return True

    async def start_vm(self, name: str) -> bool:
        await self._request("POST", f"/vms/{name}/start")
        return True

    async def stop_vm(self, name: str, force: bool = False) -> bool:
        await self._request("POST", f"/vms/{name}/stop", params={"force": force})
        return True

    async def delete_vm(self, name: str) -> bool:
        await self._request("DELETE", f"/vms/{name}")
        return True

    async def get_vm_info(self, name: str) -> VMInfo:
        data = await self._request("GET", f"/vms/{name}")
        return VMInfo(
            name=data["name"],
            status=data["status"],
            cpu_count=data["cpu_count"],
            memory_mb=data["memory_mb"],
            ip_address=data.get("ip_address")
        )

    async def list_vms(self) -> List[VMInfo]:
        data = await self._request("GET", "/vms")
        return [
            VMInfo(
                name=vm["name"],
                status=vm["status"],
                cpu_count=vm["cpu_count"],
                memory_mb=vm["memory_mb"],
                ip_address=vm.get("ip_address")
            ) for vm in data
        ]

    async def set_vm_memory(self, vm_name: str, memory_mb: int, live: bool = False) -> bool:
        await self._request("PATCH", f"/vms/{vm_name}/scale", json={"memory_mb": memory_mb, "live": live})
        return True

    async def set_vm_cpus(self, vm_name: str, cpu_count: int, live: bool = False) -> bool:
        await self._request("PATCH", f"/vms/{vm_name}/scale", json={"cpu_count": cpu_count, "live": live})
        return True

    async def enable_secure_boot(self, vm_name: str, enabled: bool) -> bool:
        await self._request("PATCH", f"/vms/{vm_name}/config", json={"secure_boot": enabled})
        return True

    async def enable_nested_virtualization(self, vm_name: str, enabled: bool) -> bool:
        await self._request("PATCH", f"/vms/{vm_name}/config", json={"nested_virt": enabled})
        return True

    async def enable_tpm(self, vm_name: str, enabled: bool) -> bool:
        await self._request("PATCH", f"/vms/{vm_name}/config", json={"tpm": enabled})
        return True

    async def create_network(self, name: str, subnet_cidr: str) -> bool:
        await self._request("POST", f"/networks/{name}", json={"cidr": subnet_cidr})
        return True

    async def delete_network(self, name: str) -> bool:
        await self._request("DELETE", f"/networks/{name}")
        return True

    async def list_networks(self) -> List[str]:
        return await self._request("GET", "/networks")

    async def get_vm_metrics(self, vm_name: str) -> "VMMetrics":
        from virtual_py.core.models import VMMetrics
        data = await self._request("GET", f"/vms/{vm_name}/metrics")
        return VMMetrics(
            cpu_usage_percent=data["cpu_usage_percent"],
            memory_demand_mb=data["memory_demand_mb"],
            uptime_seconds=data["uptime_seconds"]
        )

    # checkpoint commands over rest.
    async def create_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        await self._request("POST", f"/vms/{vm_name}/checkpoints", json={"name": checkpoint_name})
        return True

    async def restore_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        await self._request("POST", f"/vms/{vm_name}/checkpoints/{checkpoint_name}/restore")
        return True

    async def delete_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        await self._request("DELETE", f"/vms/{vm_name}/checkpoints/{checkpoint_name}")
        return True

    async def list_checkpoints(self, vm_name: str) -> List[str]:
        return await self._request("GET", f"/vms/{vm_name}/checkpoints")

    # guest command execution over rest.
    async def execute_command(self, vm_name: str, command: str, username: Optional[str] = None, password: Optional[str] = None) -> str:
        data = await self._request("POST", f"/vms/{vm_name}/execute", json={"command": command, "username": username, "password": password})
        return data["output"]

    # guest file transfer over rest.
    async def copy_file_to_guest(self, vm_name: str, host_path: str, guest_path: str, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        import base64
        with open(host_path, "rb") as f:
            content = f.read()
        b64_str = base64.b64encode(content).decode("utf-8")
        payload = {
            "guest_path": guest_path,
            "file_content_b64": b64_str,
            "username": username,
            "password": password
        }
        await self._request("POST", f"/vms/{vm_name}/copy-to-guest", json=payload)
        return True

    # disk hot-plugging over rest.
    async def attach_disk(self, vm_name: str, disk_path: str, controller_type: Optional[str] = None) -> bool:
        await self._request("POST", f"/vms/{vm_name}/disks", json={"disk_path": disk_path, "controller_type": controller_type})
        return True

    async def detach_disk(self, vm_name: str, disk_path: str) -> bool:
        await self._request("DELETE", f"/vms/{vm_name}/disks", json={"disk_path": disk_path})
        return True

    # nic hot-plugging over rest.
    async def add_network_adapter(self, vm_name: str, switch_name: str) -> str:
        data = await self._request("POST", f"/vms/{vm_name}/network-adapters", json={"switch_name": switch_name})
        return data["mac_address"]

    async def remove_network_adapter(self, vm_name: str, adapter_mac: str) -> bool:
        await self._request("DELETE", f"/vms/{vm_name}/network-adapters/{adapter_mac}")
        return True

    async def migrate_vm(self, vm_name: str, target_host: str, **kwargs) -> bool:
        await self._request("POST", f"/vms/{vm_name}/migrate", json={"target_host": target_host})
        return True

    async def create_storage_pool(self, name: str, path: str) -> bool:
        await self._request("POST", f"/storage/{name}", json={"path": path})
        return True

    async def delete_storage_pool(self, name: str) -> bool:
        await self._request("DELETE", f"/storage/{name}")
        return True

    async def list_storage_pools(self) -> List[str]:
        data = await self._request("GET", "/storage")
        return data

    async def list_snapshots(self, vm_name: str) -> List[str]:
        data = await self._request("GET", f"/vms/{vm_name}/snapshots")
        return data

    async def export_vm(self, vm_name: str, export_path: str) -> bool:
        await self._request("POST", f"/vms/{vm_name}/export", json={"export_path": export_path})
        return True

    async def clone_vm(self, vm_name: str, clone_name: str) -> bool:
        await self._request("POST", f"/vms/{vm_name}/clone", json={"clone_name": clone_name})
        return True

    async def get_console_display(self, vm_name: str) -> str:
        return await self._request("GET", f"/vms/{vm_name}/console-display")
