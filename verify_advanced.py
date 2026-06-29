import asyncio
import sys
from virtual_py import get_provider

# automation script to verify advanced VM operations like checkpoints, scaling, and IP resolution.
# todo: add test cases for guest command copy once credentials are standardized.
async def main():
    vm_name = "alpine-test"
    provider = get_provider()
    
    print(f"starting live verification on provider: {provider.__class__.__name__}")
    
    # 1. verify we can retrieve VM info (and IP address if registered).
    try:
        print("\n[1/4] querying active VM details...")
        info = await provider.get_vm_info(vm_name)
        print(f"VM info -> name: {info.name}, status: {info.status}, cpus: {info.cpu_count}, memory: {info.memory_mb}MB")
        print(f"IP address resolved: {info.ip_address}")
    except Exception as e:
        print(f"failed to query info: {e}")
        return

    # 2. scaling VM resources.
    # hyper-v doesn't support live CPU plugs, so we scale memory live and scale CPUs when stopped.
    try:
        print("\n[2/4] testing resource scaling...")
        print("scaling memory live to 768MB...")
        await provider.set_vm_memory(vm_name, 768, live=True)
        
        info = await provider.get_vm_info(vm_name)
        print(f"updated memory: {info.memory_mb}MB")
        
        # CPU scaling needs VM to be offline.
        print("stopping VM to scale CPU cores...")
        await provider.stop_vm(vm_name)
        print("scaling CPUs to 2 cores...")
        await provider.set_vm_cpus(vm_name, 2)
        
        print("restarting VM...")
        await provider.start_vm(vm_name)
        
        info = await provider.get_vm_info(vm_name)
        print(f"updated VM info -> status: {info.status}, cpus: {info.cpu_count}")
    except Exception as e:
        print(f"failed scaling check: {e}")

    # 3. checkpoint / snapshot creation.
    try:
        print("\n[3/4] testing checkpoint/snapshot features...")
        snap_name = "check-point-verify"
        print(f"creating checkpoint '{snap_name}'...")
        await provider.create_checkpoint(vm_name, snap_name)
        
        print("listing checkpoints:")
        snaps = await provider.list_checkpoints(vm_name)
        for snap in snaps:
            print(f" - {snap}")
            
        print(f"deleting checkpoint '{snap_name}'...")
        await provider.delete_checkpoint(vm_name, snap_name)
        print("checkpoint cleaned up.")
    except Exception as e:
        print(f"failed checkpoint check: {e}")

    # 4. cleanup verification.
    try:
        print("\n[4/4] listing all VMs to verify final configuration...")
        vms = await provider.list_vms()
        for vm in vms:
            if vm.name == vm_name:
                print(f"VM: {vm.name}, status: {vm.status}, memory: {vm.memory_mb}MB, cpus: {vm.cpu_count}, IP: {vm.ip_address}")
    except Exception as e:
        print(f"failed final check: {e}")

if sys.platform != "win32":
    print("this script is designed for hyper-v on windows hosts.")
    sys.exit(1)
asyncio.run(main())
