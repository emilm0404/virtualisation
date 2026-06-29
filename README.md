# virtual-py

if you have ever tried writing python code that needs to spin up virtual machines on both linux and windows, you know it is a massive headache. libvirt bindings require native c compilers that break during pip installs, and querying raw hyper-v namespaces on windows is incredibly messy.

this library provides a simple, unified, async interface to control both linux kvm and windows hyper-v. it wraps standard cli tools (virsh and powershell) asynchronously so it is lightweight, quick to install, and does not require compiling heavy compiled binaries on your host machine.

## how it works

we use the provider pattern to expose a single python class (VMProvider). at startup, the library auto-detects your host os and loads the correct driver:

* **windows host**: talks to powershell cmdlets like Get-VM and Set-VMMemory.
* **linux host**: talks to the virsh command line tool.

## what it can do

* **lifecycle operations**: create, start, stop, and force-kill virtual machines.
* **checkpoints**: create, list, delete, and restore VM snapshots.
* **guest commands**: copy files and execute terminal scripts directly inside the guest OS (uses qemu guest agent on linux and powershell direct on windows).
* **hot-plugging**: dynamically attach or detach secondary virtual disks and network interfaces.
* **scaling**: resize CPU cores and memory limits (supports active live resizing or offline updates).
* **ip address lookup**: queries guest networks to retrieve host IP addresses.
* **safe design**: validates vm names and paths against redirection and chaining sequences to block shell injection.

## code example

```python
import asyncio
import sys
from virtual_py import get_provider

async def main():
    # detects if you are on windows (hyper-v) or linux (kvm)
    provider = get_provider()
    
    # query configured vms
    vms = await provider.list_vms()
    for vm in vms:
        print(f"found vm: {vm.name} ({vm.status})")

    # provision a new machine
    disk = "C:\\VMs\\test.vhdx" if sys.platform == "win32" else "/var/lib/libvirt/images/test.qcow2"
    await provider.create_vm(
        name="my-test-vm",
        cpu_count=2,
        memory_mb=2048,
        disk_path=disk
    )
    
    # boot it up
    await provider.start_vm("my-test-vm")

if __name__ == "__main__":
    asyncio.run(main())
```

## using the cli tool

you can also manage your hypervisors directly from your terminal:

```bash
# list all local virtual machines in a table
python -m virtual_py.cli list

# list all available OS templates from the catalog
python -m virtual_py.cli catalog list

# automatically download an ISO and provision a VM
python -m virtual_py.cli create my-new-vm --os ubuntu-24.04

# capture a quick snapshot
python -m virtual_py.cli checkpoint create my-vm backup-snap

# adjust core allocations
python -m virtual_py.cli scale my-vm --cpu 4
```

## installation

install the package in editable mode from the repository root:

```bash
pip install -e .
```

## development and testing

to run unit tests (we mock virsh and powershell CLI calls so tests run cleanly anywhere):

```bash
pip install -e .[dev]
pytest
```
