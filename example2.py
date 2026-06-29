import asyncio
import os
from virtual_py import get_provider
from virtual_py.iac import apply_yaml, destroy_yaml
from virtual_py.utils.backup import create_backup

async def main():
    provider = get_provider()
    
    # write a simple config file for demonstration.
    yaml_content = """
networks:
  - name: test-net
    cidr: 192.168.150.0/24
vms:
  - name: advanced-vm
    cpu: 2
    ram: 2048
    disk: C:\\VMs\\advanced-vm.vhdx
    network: test-net
"""
    yaml_path = "iac_temp.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    print("[1/6] applying declarative configuration...")
    try:
        await apply_yaml(yaml_path)
        print("configuration applied successfully.")
    except Exception as e:
        print(f"skipping live apply (likely not running as admin/root): {e}")

    print("\n[2/6] detecting host graphics adapters...")
    gpus = await provider.detect_host_gpus()
    for idx, g in enumerate(gpus):
        print(f"found host GPU: {g.get('gpu')} | PCI: {g.get('pci_address')}")

    print("\n[3/6] attaching shared gpu-pv adapter...")
    try:
        await provider.attach_gpu("advanced-vm", mode="shared")
        print("gpu adapter attached.")
    except Exception as e:
        print(f"could not attach gpu: {e}")

    print("\n[4/6] fetching live VM metrics...")
    try:
        metrics = await provider.get_vm_metrics("advanced-vm")
        print(f"metrics -> cpu: {metrics.cpu_usage_percent}%, memory: {metrics.memory_demand_mb}MB")
    except Exception as e:
        print(f"metrics query skipped: {e}")

    print("\n[5/6] exporting VM backups...")
    backup_file = "advanced-vm-backup.tar.gz"
    try:
        await create_backup("advanced-vm", backup_file)
        print(f"backup created successfully: {backup_file}")
        if os.path.exists(backup_file):
            os.remove(backup_file)
    except Exception as e:
        print(f"backup creation skipped: {e}")

    print("\n[6/6] cleaning up infrastructure resources...")
    try:
        await destroy_yaml(yaml_path)
        print("cleanup finished.")
    except Exception as e:
        print(f"cleanup encountered error: {e}")
        
    if os.path.exists(yaml_path):
        os.remove(yaml_path)

asyncio.run(main())
