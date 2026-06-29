import asyncio
import os
import sys
import urllib.request
from virtual_py import get_provider

# automated script to set up a minimal alpine vm.
# downloads the virtual-optimized alpine iso to act as our live boot image.
async def main():
    vm_name = "alpine-test"
    iso_url = "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-virt-3.20.0-x86_64.iso"
    
    vm_dir = "C:\\VMs"
    iso_path = os.path.join(vm_dir, "alpine-virt-3.20.0-x86_64.iso")
    disk_path = os.path.join(vm_dir, "alpine-test.vhdx")
    
    if not os.path.exists(vm_dir):
        print(f"creating directory {vm_dir}...")
        os.makedirs(vm_dir, exist_ok=True)
        
    if not os.path.exists(iso_path):
        print(f"downloading alpine linux virtual iso (~50MB) from {iso_url}...")
        urllib.request.urlretrieve(iso_url, iso_path)
        print("download completed.")
    else:
        print("alpine linux iso already downloaded.")

    provider = get_provider()
    
    # purge existing alpine-test instance so this script can run repeatedly.
    try:
        print("checking if old vm exists...")
        await provider.get_vm_info(vm_name)
        print("stopping and deleting old vm...")
        await provider.stop_vm(vm_name, force=True)
        await provider.delete_vm(vm_name)
    except Exception:
        pass

    print(f"creating new vm '{vm_name}' with 512MB RAM and 1 CPU and boot ISO...")
    success = await provider.create_vm(
        name=vm_name,
        cpu_count=1,
        memory_mb=512,
        disk_path=disk_path,
        network_name="Default Switch",
        iso_path=iso_path
    )
    
    if not success:
        print("failed to create vm.")
        return
        
    print(f"starting vm '{vm_name}'...")
    await provider.start_vm(vm_name)
    
    info = await provider.get_vm_info(vm_name)
    print(f"\nsuccess! vm status: {info.name} is {info.status}")
    print("you can open hyper-v manager to see the alpine console booting.")

if __name__ == "__main__":
    if sys.platform != "win32":
        print("this script is designed for hyper-v on windows hosts only.")
        sys.exit(1)
    asyncio.run(main())
