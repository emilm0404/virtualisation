import asyncio
import os
import urllib.request
import subprocess
from virtual_py import get_provider
from virtual_py.iac import apply_yaml

async def main():
    provider = get_provider()
    
    vm_dir = "C:\\VMs"
    iso_path = os.path.join(vm_dir, "win10-eval.iso")
    
    if not os.path.exists(vm_dir):
        os.makedirs(vm_dir, exist_ok=True)
        
    # windows evaluation ISO is ~5GB. check if file exists and is not a small redirect HTML.
    if os.path.exists(iso_path) and os.path.getsize(iso_path) < 100000000:
        print("detected corrupted/incomplete ISO file. removing it...")
        os.remove(iso_path)

    if not os.path.exists(iso_path):
        print("windows 10 evaluation ISO is ~5GB.")
        print("due to microsoft's dynamic download link security, we suggest downloading the ISO manually from:")
        print("https://www.microsoft.com/en-us/evalcenter/download-windows-10-enterprise")
        print(f"once downloaded, save it to: {iso_path}")
        print("waiting for manual file placement...")
        while not os.path.exists(iso_path) or os.path.getsize(iso_path) < 100000000:
            await asyncio.sleep(2)
        print("valid ISO file detected. resuming setup...")
    else:
        print("windows 10 evaluation ISO already present.")

    try:
        await provider.stop_vm("win-advanced-vm", force=True)
        await provider.delete_vm("win-advanced-vm")
    except Exception:
        pass

    yaml_content = f"""
networks:
  - name: test-net
    cidr: 192.168.150.0/24
vms:
  - name: win-advanced-vm
    cpu: 2
    ram: 4096
    disk: C:\\VMs\\win-advanced-vm.vhdx
    network: test-net
    iso: {iso_path.replace('\\', '\\\\')}
"""
    yaml_path = "iac_win_temp.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    print("[1/4] applying declarative configuration (recreating stopped VM)...")
    await apply_yaml(yaml_path)
    print("configuration applied successfully.")

    print("\n[2/4] attaching shared GPU-PV adapter...")
    await provider.attach_gpu("win-advanced-vm", mode="shared")
    print("GPU adapter attached successfully (checkpoints disabled).")

    print("\n[3/4] starting VM and launching graphical console...")
    await provider.start_vm("win-advanced-vm")
    subprocess.Popen(["vmconnect.exe", "localhost", "win-advanced-vm"])
    print("launched vmconnect console window.")
    
    await asyncio.sleep(3)
    metrics = await provider.get_vm_metrics("win-advanced-vm")
    print(f"metrics -> cpu: {metrics.cpu_usage_percent}%, memory: {metrics.memory_demand_mb}MB")

    if os.path.exists(yaml_path):
        os.remove(yaml_path)

asyncio.run(main())
