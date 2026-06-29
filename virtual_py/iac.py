import yaml
from virtual_py import get_provider

async def apply_yaml(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # get default local provider.
    provider = get_provider()

    # deploy networks first.
    networks = config.get("networks", [])
    for net in networks:
        name = net.get("name")
        cidr = net.get("cidr", "192.168.100.0/24")
        if name:
            existing = await provider.list_networks()
            if name not in existing:
                await provider.create_network(name, cidr)

    # deploy virtual machines.
    vms = config.get("vms", [])
    for vm in vms:
        name = vm.get("name")
        if not name:
            continue
        
        cpu = vm.get("cpu", 1)
        ram = vm.get("ram", 1024)
        disk = vm.get("disk")
        network = vm.get("network")
        iso = vm.get("iso")
        
        try:
            # check if vm exists.
            await provider.get_vm_info(name)
            # scale VM if running state differs.
            await provider.set_vm_memory(name, ram, live=True)
            await provider.set_vm_cpus(name, cpu, live=False)
        except Exception:
            # create vm if it does not exist.
            await provider.create_vm(
                name=name,
                cpu_count=cpu,
                memory_mb=ram,
                disk_path=disk,
                network_name=network,
                iso_path=iso
            )

async def destroy_yaml(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    provider = get_provider()

    # destroy vms.
    vms = config.get("vms", [])
    for vm in vms:
        name = vm.get("name")
        if name:
            try:
                await provider.stop_vm(name, force=True)
                await provider.delete_vm(name)
            except Exception:
                pass

    # destroy networks.
    networks = config.get("networks", [])
    for net in networks:
        name = net.get("name")
        if name:
            try:
                await provider.delete_network(name)
            except Exception:
                pass
