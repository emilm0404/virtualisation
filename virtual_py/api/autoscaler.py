import asyncio
from virtual_py import get_provider
from virtual_py.core.models import VMStatus

class Autoscaler:
    def __init__(self, interval_seconds: int = 10):
        self.interval_seconds = interval_seconds
        self.running = False
        self.task = None

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        provider = get_provider()
        while self.running:
            try:
                vms = await provider.list_vms()
                for vm in vms:
                    if vm.status != VMStatus.RUNNING:
                        continue
                    
                    # fetch metrics for the active VM.
                    try:
                        metrics = await provider.get_vm_metrics(vm.name)
                        # scale memory if VM is running low.
                        if metrics.memory_demand_mb > (vm.memory_mb * 0.85):
                            new_memory = vm.memory_mb + 256
                            if new_memory <= 8192:
                                await provider.set_vm_memory(vm.name, new_memory, live=True)
                        elif metrics.memory_demand_mb < (vm.memory_mb * 0.30):
                            new_memory = vm.memory_mb - 256
                            if new_memory >= 512:
                                await provider.set_vm_memory(vm.name, new_memory, live=True)
                    except Exception:
                        pass
            except Exception:
                pass
            await asyncio.sleep(self.interval_seconds)
