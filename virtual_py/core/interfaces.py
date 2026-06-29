import abc
from typing import List, Optional
import asyncio
from .models import VMInfo

# interface for all hypervisor wrappers.
# if you write a new provider (e.g. vmware or virtualbox), inherit from this.
class VMProvider(abc.ABC):

    @abc.abstractmethod
    async def create_vm(
        self,
        name: str,
        cpu_count: int,
        memory_mb: int,
        disk_path: str,
        network_name: Optional[str] = None,
        iso_path: Optional[str] = None,
        cloud_init: Optional[dict] = None,
        raw_user_data: Optional[str] = None,
        sysprep: Optional[dict] = None,
        **kwargs
    ) -> bool:
        pass

    @abc.abstractmethod
    async def start_vm(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    async def stop_vm(self, name: str, force: bool = False) -> bool:
        pass

    @abc.abstractmethod
    async def delete_vm(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    async def get_vm_info(self, name: str) -> VMInfo:
        pass

    @abc.abstractmethod
    async def list_vms(self) -> List[VMInfo]:
        pass

    @abc.abstractmethod
    async def create_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        pass

    @abc.abstractmethod
    async def restore_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        pass

    @abc.abstractmethod
    async def delete_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        pass

    @abc.abstractmethod
    async def list_checkpoints(self, vm_name: str) -> List[str]:
        pass

    @abc.abstractmethod
    async def execute_command(
        self,
        vm_name: str,
        command: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> str:
        pass

    @abc.abstractmethod
    async def copy_file_to_guest(
        self,
        vm_name: str,
        host_path: str,
        guest_path: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> bool:
        pass

    @abc.abstractmethod
    async def set_vm_memory(self, vm_name: str, memory_mb: int, live: bool = False) -> bool:
        pass

    @abc.abstractmethod
    async def set_vm_cpus(self, vm_name: str, cpu_count: int, live: bool = False) -> bool:
        pass

    @abc.abstractmethod
    async def attach_disk(self, vm_name: str, disk_path: str, controller_type: Optional[str] = None) -> bool:
        pass

    @abc.abstractmethod
    async def detach_disk(self, vm_name: str, disk_path: str) -> bool:
        pass

    @abc.abstractmethod
    async def add_network_adapter(self, vm_name: str, switch_name: str) -> str:
        pass

    @abc.abstractmethod
    async def remove_network_adapter(self, vm_name: str, adapter_mac: str) -> bool:
        pass

    # --- Advanced Configuration ---
    @abc.abstractmethod
    async def enable_secure_boot(self, vm_name: str, enabled: bool) -> bool:
        pass

    @abc.abstractmethod
    async def enable_nested_virtualization(self, vm_name: str, enabled: bool) -> bool:
        pass

    @abc.abstractmethod
    async def enable_tpm(self, vm_name: str, enabled: bool) -> bool:
        pass

    # --- Virtual Network Management ---
    @abc.abstractmethod
    async def create_network(self, name: str, subnet_cidr: str) -> bool:
        pass

    @abc.abstractmethod
    async def delete_network(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    async def list_networks(self) -> List[str]:
        pass

    # --- Telemetry & Metrics ---
    @abc.abstractmethod
    async def get_vm_metrics(self, vm_name: str) -> "VMMetrics":
        pass

    # --- Live VM Migration ---
    @abc.abstractmethod
    async def migrate_vm(self, vm_name: str, target_host: str, **kwargs) -> bool:
        pass

    # --- Storage Pools ---
    @abc.abstractmethod
    async def create_storage_pool(self, name: str, path: str) -> bool:
        pass

    @abc.abstractmethod
    async def delete_storage_pool(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    async def list_storage_pools(self) -> List[str]:
        pass

    # standard polling helper. retries every 2 seconds until an ip appears or timeout occurs.
    async def wait_for_ip(self, vm_name: str, timeout: int = 60) -> str:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                info = await self.get_vm_info(vm_name)
                if info.ip_address:
                    return info.ip_address
            except Exception:
                pass
            await asyncio.sleep(2)
        raise TimeoutError(f"timed out waiting for vm '{vm_name}' to obtain an ip address.")

    # --- Snapshot Management ---
    @abc.abstractmethod
    async def list_snapshots(self, vm_name: str) -> List[str]:
        pass

    # --- VM Export / Clone ---
    @abc.abstractmethod
    async def export_vm(self, vm_name: str, export_path: str) -> bool:
        pass

    @abc.abstractmethod
    async def clone_vm(self, vm_name: str, clone_name: str) -> bool:
        pass
