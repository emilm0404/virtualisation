import asyncio
import os
import urllib.request
import subprocess
from virtual_py import get_provider
from virtual_py.iac import apply_yaml
from virtual_py.utils.backup import create_backup

async def main():
    provider = get_provider()
    
    vm_dir = "C:\\VMs"
    iso_path = os.path.join(vm_dir, "alpine-virt-3.20.0-x86_64.iso")
    
    if not os.path.exists(vm_dir):
        os.makedirs(vm_dir, exist_ok=True)
        
    if not os.path.exists(iso_path):
        print("downloading alpine boot image (~50MB)...")
        iso_url = "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-virt-3.20.0-x86_64.iso"
        urllib.request.urlretrieve(iso_url, iso_path)
        print("download completed.")

    # clean up previous VM instance if exists to allow clean recreate.
    try:
        await provider.stop_vm("advanced-vm", force=True)
        await provider.delete_vm("advanced-vm")
    except Exception:
        pass

    yaml_content = f"""
networks:
  - name: test-net
    cidr: 192.168.150.0/24
vms:
  - name: advanced-vm
    cpu: 2
    ram: 2048
    disk: C:\\VMs\\advanced-vm.vhdx
    network: test-net
    iso: {iso_path.replace('\\', '\\\\')}
"""
    yaml_path = "iac_temp.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    print("[1/5] applying declarative configuration (recreating stopped VM)...")
    await apply_yaml(yaml_path)
    print("configuration applied successfully.")

    print("\n[2/5] detecting host graphics adapters...")
    gpus = await provider.detect_host_gpus()
    for idx, g in enumerate(gpus):
        print(f"found host GPU: {g.get('gpu')} | PCI: {g.get('pci_address')}")

    print("\n[3/5] attaching shared gpu-pv adapter...")
    await provider.attach_gpu("advanced-vm", mode="shared")
    print("gpu adapter attached successfully.")

    print("\n[4/5] exporting VM backup (while offline to avoid file locks)...")
    backup_file = "advanced-vm-backup.tar.gz"
    try:
        await create_backup("advanced-vm", backup_file)
        print(f"backup created successfully: {backup_file}")
        if os.path.exists(backup_file):
            os.remove(backup_file)
    except Exception as e:
        print(f"backup creation skipped: {e}")

    print("\n[5/5] starting VM, launching console window, and checking metrics...")
    await provider.start_vm("advanced-vm")
    
    # launch the interactive virtual machine connection graphical console on windows.
    subprocess.Popen(["vmconnect.exe", "localhost", "advanced-vm"])
    print("launched vmconnect console window.")
    
    await asyncio.sleep(3)
    metrics = await provider.get_vm_metrics("advanced-vm")
    print(f"metrics -> cpu: {metrics.cpu_usage_percent}%, memory: {metrics.memory_demand_mb}MB")

    print("\nVM is running with GPU paravirtualization.")
    print("To test the GPU inside the guest:")
    print("1. Log in to the console using username 'root' (no password).")
    print("2. Run: dmesg | grep -i -E 'drm|virtio-gpu|hyperv_fb|hyper-v'")
    print("3. Run: find /sys/devices -name '*gpu*' to check GPU detection inside Linux.")

    if os.path.exists(yaml_path):
        os.remove(yaml_path)

asyncio.run(main())
