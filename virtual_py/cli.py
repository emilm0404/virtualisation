import argparse
import asyncio
import json
import sys
from typing import List
import os
from virtual_py import get_provider
from virtual_py.core.exceptions import VMException
from virtual_py.catalog import default_registry, download_iso_async

async def handle_list(args, provider):
    vms = await provider.list_vms()
    if args.json:
        print(json.dumps([vm.to_dict() for vm in vms], indent=2))
        return
        
    if not vms:
        print("no virtual machines found.")
        return
    print(f"{'Name':<30} {'State':<12} {'Memory (MB)':<12} {'CPUs':<6} {'IP Address':<15}")
    print("-" * 80)
    for vm in vms:
        ip = vm.ip_address or "-"
        print(f"{vm.name:<30} {vm.status:<12} {vm.memory_mb:<12} {vm.cpu_count:<6} {ip:<15}")

async def handle_info(args, provider):
    try:
        info = await provider.get_vm_info(args.name)
        if args.json:
            print(json.dumps(info.to_dict(), indent=2))
            return
        print(f"VM Name:        {info.name}")
        print(f"Status:         {info.status}")
        print(f"Memory size:    {info.memory_mb} MB")
        print(f"CPU count:      {info.cpu_count}")
        print(f"IP address:     {info.ip_address or '-'}")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_start(args, provider):
    try:
        print(f"starting vm '{args.name}'...")
        await provider.start_vm(args.name)
        print("vm started successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_stop(args, provider):
    try:
        print(f"stopping vm '{args.name}' (force={args.force})...")
        await provider.stop_vm(args.name, force=args.force)
        print("vm stopped successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_delete(args, provider):
    try:
        print(f"deleting vm '{args.name}' and cleaning up storage...")
        await provider.delete_vm(args.name)
        print("vm deleted successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_checkpoint(args, provider):
    try:
        if args.checkpoint_action == "create":
            print(f"creating checkpoint '{args.checkpoint_name}' for VM '{args.name}'...")
            await provider.create_checkpoint(args.name, args.checkpoint_name)
            print("checkpoint created.")
        elif args.checkpoint_action == "restore":
            print(f"restoring VM '{args.name}' to checkpoint '{args.checkpoint_name}'...")
            await provider.restore_checkpoint(args.name, args.checkpoint_name)
            print("checkpoint restored.")
        elif args.checkpoint_action == "delete":
            print(f"deleting checkpoint '{args.checkpoint_name}' for VM '{args.name}'...")
            await provider.delete_checkpoint(args.name, args.checkpoint_name)
            print("checkpoint deleted.")
        elif args.checkpoint_action == "list":
            snaps = await provider.list_checkpoints(args.name)
            if args.json:
                print(json.dumps(snaps))
                return
            if not snaps:
                print("no checkpoints found.")
                return
            print("checkpoints:")
            for snap in snaps:
                print(f" - {snap}")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_scale(args, provider):
    try:
        if args.ram:
            print(f"scaling memory to {args.ram}MB (live={args.live})...")
            await provider.set_vm_memory(args.name, args.ram, live=args.live)
        if args.cpu:
            print(f"scaling CPUs to {args.cpu} cores (live={args.live})...")
            await provider.set_vm_cpus(args.name, args.cpu, live=args.live)
        print("scale operation complete.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_network(args, provider):
    try:
        if args.network_action == "list":
            networks = await provider.list_networks()
            if args.json:
                print(json.dumps(networks))
                return
            if not networks:
                print("no networks found.")
                return
            print("networks:")
            for n in networks:
                print(f" - {n}")
        elif args.network_action == "create":
            print(f"creating network '{args.network_name}' with cidr '{args.cidr}'...")
            await provider.create_network(args.network_name, args.cidr)
            print("network created.")
        elif args.network_action == "delete":
            print(f"deleting network '{args.network_name}'...")
            await provider.delete_network(args.network_name)
            print("network deleted.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_config(args, provider):
    try:
        if args.secure_boot is not None:
            print(f"setting secure boot to {args.secure_boot}...")
            await provider.enable_secure_boot(args.name, args.secure_boot)
        if args.nested_virt is not None:
            print(f"setting nested virtualization to {args.nested_virt}...")
            await provider.enable_nested_virtualization(args.name, args.nested_virt)
        if args.tpm is not None:
            print(f"setting tpm to {args.tpm}...")
            await provider.enable_tpm(args.name, args.tpm)
        print("configuration complete.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_metrics(args, provider):
    try:
        metrics = await provider.get_vm_metrics(args.name)
        if args.json:
            print(json.dumps({
                "cpu_usage_percent": metrics.cpu_usage_percent,
                "memory_demand_mb": metrics.memory_demand_mb,
                "uptime_seconds": metrics.uptime_seconds
            }, indent=2))
            return
        print(f"Metrics for VM '{args.name}':")
        print(f"  CPU Usage:       {metrics.cpu_usage_percent}%")
        print(f"  Memory Demand:   {metrics.memory_demand_mb} MB")
        print(f"  Uptime (sec):    {metrics.uptime_seconds}")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_migrate(args, provider):
    try:
        print(f"migrating vm '{args.name}' to destination host '{args.target_host}'...")
        await provider.migrate_vm(args.name, args.target_host)
        print(f"vm '{args.name}' migrated successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_storage(args, provider):
    try:
        if args.storage_action == "list":
            pools = await provider.list_storage_pools()
            if args.json:
                print(json.dumps(pools))
            else:
                if not pools:
                    print("no storage pools found.")
                else:
                    print(f"{'pool name':<30}")
                    print("-" * 30)
                    for p in pools:
                        print(f"{p:<30}")
        elif args.storage_action == "create":
            await provider.create_storage_pool(args.storage_name, args.path)
            print(f"storage pool '{args.storage_name}' created at '{args.path}'.")
        elif args.storage_action == "delete":
            await provider.delete_storage_pool(args.storage_name)
            print(f"storage pool '{args.storage_name}' deleted.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

# clones a VM using name and clone_name.
async def handle_clone(args, provider):
    try:
        print(f"cloning vm '{args.name}' to '{args.clone_name}'...")
        await provider.clone_vm(args.name, args.clone_name)
        print("vm cloned successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

# exports a VM to export_path.
async def handle_export(args, provider):
    try:
        print(f"exporting vm '{args.name}' to '{args.export_path}'...")
        await provider.export_vm(args.name, args.export_path)
        print("vm exported successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

# runs shell command in guest OS.
async def handle_execute(args, provider):
    try:
        print(f"executing command on vm '{args.name}'...")
        out = await provider.execute_command(
            args.name, args.guest_command,
            username=args.username, password=args.password
        )
        sys.stdout.write(out)
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

# copies host file to guest path.
async def handle_copy(args, provider):
    try:
        print(f"copying '{args.host_path}' to '{args.guest_path}' inside vm '{args.name}'...")
        await provider.copy_file_to_guest(
            args.name, args.host_path, args.guest_path,
            username=args.username, password=args.password
        )
        print("file copied successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

# manages hot-plugging of devices.
async def handle_device(args, provider):
    try:
        if args.device_action == "attach-disk":
            print(f"attaching disk '{args.disk_path}' to vm '{args.name}'...")
            await provider.attach_disk(args.name, args.disk_path, controller_type=args.controller)
            print("disk attached successfully.")
        elif args.device_action == "detach-disk":
            print(f"detaching disk '{args.disk_path}' from vm '{args.name}'...")
            await provider.detach_disk(args.name, args.disk_path)
            print("disk detached successfully.")
        elif args.device_action == "attach-nic":
            print(f"attaching nic switch '{args.switch_name}' to vm '{args.name}'...")
            mac = await provider.add_network_adapter(args.name, args.switch_name)
            print(f"nic attached successfully. mac address: {mac}")
        elif args.device_action == "detach-nic":
            print(f"detaching nic mac '{args.mac}' from vm '{args.name}'...")
            await provider.remove_network_adapter(args.name, args.mac)
            print("nic detached successfully.")
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

def handle_daemon(args):
    import uvicorn
    print(f"Starting virtual-pyd daemon on {args.host}:{args.port}...")
    uvicorn.run("virtual_py.api.server:app", host=args.host, port=args.port, reload=False)

async def handle_cluster_create(args):
    from virtual_py.api.cluster import ClusterManager
    nodes = [n.strip() for n in args.nodes.split(",")]
    print(f"Checking load across {len(nodes)} nodes in cluster...")
    manager = ClusterManager(nodes)
    best_node = await manager.get_least_loaded_node()
    if not best_node:
        print("error: All cluster nodes are unreachable or down.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Selected least loaded node: {best_node}")
    try:
        from virtual_py import get_provider
        provider = get_provider("remote", base_url=best_node)
        
        # Parse cloud-init JSON if provided
        cloud_init = None
        if getattr(args, 'cloud_init', None):
            cloud_init = json.loads(args.cloud_init)
            
        print(f"Deploying VM '{args.name}' to {best_node}...")
        success = await provider.create_vm(
            name=args.name,
            cpu_count=args.cpus,
            memory_mb=args.memory,
            disk_path=args.disk,
            iso_path=getattr(args, 'iso', None),
            cloud_init=cloud_init
        )
        if success:
            print(f"Successfully clustered VM '{args.name}' on '{best_node}'.")
    except Exception as e:
        print(f"error deploying to cluster node {best_node}: {e}", file=sys.stderr)
        sys.exit(1)

async def handle_catalog(args):
    if args.catalog_action == "list":
        templates = default_registry.list_all()
        if args.json:
            print(json.dumps([{"id": t.id, "name": t.name, "url": t.url} for t in templates], indent=2))
            return
        if not templates:
            print("No templates found in catalog.")
            return
        print(f"{'ID':<15} {'Name':<40} {'Min RAM':<10} {'Min CPU'}")
        print("-" * 80)
        for t in templates:
            print(f"{t.id:<15} {t.name:<40} {t.min_memory_mb:<10} {t.min_cpu_count}")

async def handle_create(args, provider):
    try:
        # Read raw user data if filepath is provided
        raw_user_data = None
        if getattr(args, 'raw_user_data', None):
            if os.path.exists(args.raw_user_data):
                with open(args.raw_user_data, 'r', encoding='utf-8') as f:
                    raw_user_data = f.read()
            else:
                print(f"error: raw user data file '{args.raw_user_data}' not found.", file=sys.stderr)
                sys.exit(1)

        # Parse cloud-init JSON if provided
        cloud_init = None
        if getattr(args, 'cloud_init', None):
            cloud_init = json.loads(args.cloud_init)

        # Parse sysprep JSON if provided
        sysprep = None
        if getattr(args, 'sysprep', None):
            sysprep = json.loads(args.sysprep)

        if args.os:
            tpl = default_registry.get(args.os)
            if not tpl:
                print(f"error: template '{args.os}' not found in catalog.", file=sys.stderr)
                sys.exit(1)
            
            memory = args.ram or tpl.min_memory_mb
            cpu = args.cpu or tpl.min_cpu_count
            
            print(f"provisioning from catalog template '{tpl.name}'...")
            
            iso_cache_dir = os.path.expanduser("~/.virtual_py/images")
            iso_path = os.path.join(iso_cache_dir, os.path.basename(tpl.url))
            
            if not os.path.exists(iso_path):
                print(f"downloading {tpl.url} to {iso_path}...")
                await download_iso_async(tpl.url, iso_path)
                print("download complete.")
                
            if tpl.cloud_init_supported and not cloud_init and not raw_user_data:
                cloud_init = {
                    "hostname": args.name,
                    "username": tpl.default_username,
                    "password": "password"
                }
            
            disk_path = args.disk
            if not disk_path:
                disk_path = os.path.join(os.path.expanduser("~/.virtual_py/vms"), f"{args.name}.vhdx" if sys.platform == "win32" else f"{args.name}.qcow2")
                
            print(f"creating vm '{args.name}'...")
            await provider.create_vm(
                name=args.name,
                cpu_count=cpu,
                memory_mb=memory,
                disk_path=disk_path,
                network_name=args.network,
                iso_path=iso_path,
                cloud_init=cloud_init,
                raw_user_data=raw_user_data,
                sysprep=sysprep
            )
            print("vm created successfully.")
            
        else:
            if not args.disk:
                print("error: --disk is required when not using a catalog template.", file=sys.stderr)
                sys.exit(1)
            
            memory = args.ram or 1024
            cpu = args.cpu or 1
            
            print(f"creating vm '{args.name}'...")
            await provider.create_vm(
                name=args.name,
                cpu_count=cpu,
                memory_mb=memory,
                disk_path=args.disk,
                network_name=args.network,
                iso_path=args.iso,
                cloud_init=cloud_init,
                raw_user_data=raw_user_data,
                sysprep=sysprep
            )
            print("vm created successfully.")
            
    except VMException as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

async def run():
    parser = argparse.ArgumentParser(
        description="virtual-py CLI VM manager",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--provider", help="override default provider ('kvm' or 'hyperv')")
    parser.add_argument("--remote", help="URL of a remote virtual-pyd daemon (e.g. http://192.168.1.100:8080)")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = subparsers.add_parser("list", help="list all virtual machines")
    list_p.add_argument("--json", action="store_true", help="output in json format")

    # info
    info_p = subparsers.add_parser("info", help="get details of a single vm")
    info_p.add_argument("name", help="name of the vm")
    info_p.add_argument("--json", action="store_true", help="output in json format")

    # start
    start_p = subparsers.add_parser("start", help="boot up a vm")
    start_p.add_argument("name", help="name of the vm")

    # stop
    stop_p = subparsers.add_parser("stop", help="stop a running vm")
    stop_p.add_argument("name", help="name of the vm")
    stop_p.add_argument("--force", action="store_true", help="force immediately poweroff")

    # delete
    delete_p = subparsers.add_parser("delete", help="delete a vm and its storage")
    delete_p.add_argument("name", help="name of the vm")

    # checkpoint
    chk_p = subparsers.add_parser("checkpoint", help="manage checkpoints/snapshots")
    chk_p.add_argument("checkpoint_action", choices=["create", "restore", "delete", "list"], help="action to perform")
    chk_p.add_argument("name", help="name of the vm")
    chk_p.add_argument("checkpoint_name", nargs="?", help="name of the checkpoint")
    chk_p.add_argument("--json", action="store_true", help="output in json format (for list only)")

    # scale
    scale_p = subparsers.add_parser("scale", help="resize VM memory or cpus")
    scale_p.add_argument("name", help="name of the vm")
    scale_p.add_argument("--ram", type=int, help="new memory size in MB")
    scale_p.add_argument("--cpu", type=int, help="new cpu core count")
    scale_p.add_argument("--live", action="store_true", help="scale live without offline restart")

    # catalog
    cat_p = subparsers.add_parser("catalog", help="manage os templates")
    cat_p.add_argument("catalog_action", choices=["list"], help="action to perform")
    cat_p.add_argument("--json", action="store_true", help="output in json format")

    # create
    create_p = subparsers.add_parser("create", help="create a new vm")
    create_p.add_argument("name", help="name of the vm")
    create_p.add_argument("--os", help="catalog template id to provision from")
    create_p.add_argument("--disk", help="path to virtual disk file (auto-generated if using --os)")
    create_p.add_argument("--iso", help="path to boot iso")
    create_p.add_argument("--ram", type=int, help="memory size in MB")
    create_p.add_argument("--cpu", type=int, help="cpu core count")
    create_p.add_argument("--network", help="virtual switch or network name")
    create_p.add_argument("--cloud-init", help="json string for cloud-init config")
    create_p.add_argument("--raw-user-data", help="path to a file containing raw cloud-init user-data")
    create_p.add_argument("--sysprep", help="json string containing sysprep config (e.g. '{\"admin_password\": \"...\"}')")

    # network
    net_p = subparsers.add_parser("network", help="manage virtual networks")
    net_p.add_argument("network_action", choices=["list", "create", "delete"], help="action to perform")
    net_p.add_argument("network_name", nargs="?", help="name of the network")
    net_p.add_argument("--cidr", default="192.168.100.0/24", help="subnet CIDR (for create only)")
    net_p.add_argument("--json", action="store_true", help="output in json format (for list only)")

    # config
    cfg_p = subparsers.add_parser("config", help="configure advanced vm features")
    cfg_p.add_argument("name", help="name of the vm")
    cfg_p.add_argument("--secure-boot", type=lambda x: (str(x).lower() == 'true'), help="enable/disable secure boot (true/false)")
    cfg_p.add_argument("--nested-virt", type=lambda x: (str(x).lower() == 'true'), help="enable/disable nested virtualization (true/false)")
    cfg_p.add_argument("--tpm", type=lambda x: (str(x).lower() == 'true'), help="enable/disable vTPM (true/false)")

    # metrics
    met_p = subparsers.add_parser("metrics", help="get live telemetry for a vm")
    met_p.add_argument("name", help="name of the vm")
    met_p.add_argument("--json", action="store_true", help="output in json format")

    # migrate
    migrate_p = subparsers.add_parser("migrate", help="live migrate a vm to another host")
    migrate_p.add_argument("name", help="name of the vm")
    migrate_p.add_argument("target_host", help="hostname or IP of the destination host")

    # storage
    storage_p = subparsers.add_parser("storage", help="manage storage pools")
    storage_p.add_argument("storage_action", choices=["list", "create", "delete"], help="action to perform")
    storage_p.add_argument("storage_name", nargs="?", help="name of the storage pool")
    storage_p.add_argument("--path", help="directory path for the storage pool (for create only)")
    storage_p.add_argument("--json", action="store_true", help="output in json format (for list only)")

    # daemon
    daemon_p = subparsers.add_parser("daemon", help="start the virtual-pyd background API service")
    daemon_p.add_argument("daemon_action", choices=["start"], help="action to perform")
    daemon_p.add_argument("--host", default="0.0.0.0", help="host IP to bind to")
    daemon_p.add_argument("--port", type=int, default=8080, help="port to bind to")

    # cluster-create
    cluster_p = subparsers.add_parser("cluster-create", help="deploy a vm to the least loaded node in a cluster")
    cluster_p.add_argument("name", help="name of the vm")
    cluster_p.add_argument("--nodes", required=True, help="comma-separated list of virtual-pyd node URLs")
    cluster_p.add_argument("--cpus", type=int, default=2, help="number of cpus")
    cluster_p.add_argument("--memory", type=int, default=2048, help="memory in mb")
    cluster_p.add_argument("--disk", required=True, help="path to disk image")
    cluster_p.add_argument("--iso", help="path to boot iso")
    cluster_p.add_argument("--cloud-init", help="json string for cloud-init config")

    # clone
    clone_p = subparsers.add_parser("clone", help="clone an existing vm")
    clone_p.add_argument("name", help="name of the vm to clone")
    clone_p.add_argument("clone_name", help="name of the new clone")

    # export
    export_p = subparsers.add_parser("export", help="export vm configuration and disk")
    export_p.add_argument("name", help="name of the vm to export")
    export_p.add_argument("export_path", help="target directory path on the host")

    # execute
    exec_p = subparsers.add_parser("execute", help="execute command in guest os")
    exec_p.add_argument("name", help="name of the vm")
    exec_p.add_argument("guest_command", help="shell command string to execute")
    exec_p.add_argument("--username", help="guest administrator/root username")
    exec_p.add_argument("--password", help="guest administrator/root password")

    # copy
    copy_p = subparsers.add_parser("copy", help="copy file to guest os")
    copy_p.add_argument("name", help="name of the vm")
    copy_p.add_argument("host_path", help="local file path on host")
    copy_p.add_argument("guest_path", help="target file path inside guest")
    copy_p.add_argument("--username", help="guest administrator/root username")
    copy_p.add_argument("--password", help="guest administrator/root password")

    # device hot-plugging
    dev_p = subparsers.add_parser("device", help="manage hardware devices (disks, nics)")
    dev_p.add_argument("device_action", choices=["attach-disk", "detach-disk", "attach-nic", "detach-nic"], help="action to perform")
    dev_p.add_argument("name", help="name of the vm")
    dev_p.add_argument("--disk-path", help="disk file path (for attach/detach disk)")
    dev_p.add_argument("--controller", help="controller type (for attach-disk only)")
    dev_p.add_argument("--switch-name", help="network switch/bridge name (for attach-nic only)")
    dev_p.add_argument("--mac", help="nic MAC address (for detach-nic only)")

    args = parser.parse_args()
    
    if args.command == "daemon":
        handle_daemon(args)
        sys.exit(0)
    
    if args.command == "cluster-create":
        await handle_cluster_create(args)
        sys.exit(0)

    # initialize the hypervisor driver provider if not a catalog command.
    provider = None
    if args.command not in ["catalog", "daemon", "cluster-create"]:
        try:
            if args.remote:
                provider = get_provider("remote", base_url=args.remote)
            else:
                provider = get_provider(args.provider)
        except Exception as e:
            print(f"error initializing provider: {e}", file=sys.stderr)
            sys.exit(1)

    if args.command == "list":
        await handle_list(args, provider)
    elif args.command == "info":
        await handle_info(args, provider)
    elif args.command == "start":
        await handle_start(args, provider)
    elif args.command == "stop":
        await handle_stop(args, provider)
    elif args.command == "delete":
        await handle_delete(args, provider)
    elif args.command == "checkpoint":
        if args.checkpoint_action in ["create", "restore", "delete"] and not args.checkpoint_name:
            parser.error(f"checkpoint_name is required for action '{args.checkpoint_action}'")
        await handle_checkpoint(args, provider)
    elif args.command == "scale":
        if not args.ram and not args.cpu:
            parser.error("must specify at least --ram or --cpu to scale.")
        await handle_scale(args, provider)
    elif args.command == "catalog":
        await handle_catalog(args)
    elif args.command == "create":
        await handle_create(args, provider)
    elif args.command == "network":
        if args.network_action in ["create", "delete"] and not args.network_name:
            parser.error(f"network_name is required for action '{args.network_action}'")
        await handle_network(args, provider)
    elif args.command == "config":
        await handle_config(args, provider)
    elif args.command == "metrics":
        await handle_metrics(args, provider)
    elif args.command == "migrate":
        await handle_migrate(args, provider)
    elif args.command == "storage":
        if args.storage_action in ["create", "delete"] and not args.storage_name:
            parser.error(f"storage_name is required for action '{args.storage_action}'")
        if args.storage_action == "create" and not args.path:
            parser.error("--path is required for storage pool creation")
        await handle_storage(args, provider)
    elif args.command == "clone":
        await handle_clone(args, provider)
    elif args.command == "export":
        await handle_export(args, provider)
    elif args.command == "execute":
        await handle_execute(args, provider)
    elif args.command == "copy":
        await handle_copy(args, provider)
    elif args.command == "device":
        if args.device_action in ["attach-disk", "detach-disk"] and not args.disk_path:
            parser.error(f"--disk-path is required for action '{args.device_action}'")
        if args.device_action == "attach-nic" and not args.switch_name:
            parser.error("--switch-name is required for action 'attach-nic'")
        if args.device_action == "detach-nic" and not args.mac:
            parser.error("--mac is required for action 'detach-nic'")
        await handle_device(args, provider)

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()
