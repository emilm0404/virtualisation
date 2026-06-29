import asyncio
import sys
from virtual_py import get_provider

# quick script to test that auto detection and querying works on the host computer.
async def main():
    print(f"detected platform: {sys.platform}")
    
    provider = get_provider()
    print(f"using provider: {provider.__class__.__name__}")
    
    try:
        print("\nlisting existing virtual machines...")
        vms = await provider.list_vms()
        if not vms:
            print("no virtual machines found.")
        for vm in vms:
            print(f" - name: {vm.name}, status: {vm.status}, memory: {vm.memory_mb}MB, cpus: {vm.cpu_count}")
    except Exception as e:
        print(f"could not list vms because: {e}")

asyncio.run(main())
