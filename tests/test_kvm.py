import os
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from virtual_py import get_provider
from virtual_py.core.exceptions import VMNotFoundError, VMAlreadyExistsError, HypervisorExecutionError
from virtual_py.core.models import VMStatus

# mock helper to inject outputs to python's asyncio subprocess execution.
def make_mock_process(returncode=0, stdout=b"", stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, stderr)
    return proc

# checks that we parse multiple lines of 'virsh list' and corresponding 'virsh dominfo' correctly.
@pytest.mark.asyncio
async def test_kvm_list_vms():
    provider = get_provider("kvm")
    
    list_stdout = (
        b" Id    Name                           State\n"
        b"----------------------------------------------------\n"
        b" 1     my-running-vm                  running\n"
        b" -     my-stopped-vm                  shut off\n"
    )
    
    dominfo_running = (
        b"Name:           my-running-vm\n"
        b"UUID:           847df3be-17b5-4a57-b08e-324d6735e5be\n"
        b"OS Type:        hvm\n"
        b"State:          running\n"
        b"CPU(s):         4\n"
        b"Max memory:     4194304 kiB\n"
        b"Used memory:    4194304 kiB\n"
    )
    
    dominfo_stopped = (
        b"Name:           my-stopped-vm\n"
        b"UUID:           c78f1422-9014-41d6-8bbf-8547fae322ef\n"
        b"OS Type:        hvm\n"
        b"State:          shut off\n"
        b"CPU(s):         2\n"
        b"Max memory:     2097152 kiB\n"
        b"Used memory:    0 kiB\n"
    )

    domifaddr_stdout = (
        b" Name       MAC Address          Protocol     Address\n"
        b"-------------------------------------------------------------------------\n"
        b" vnet0      52:54:00:12:34:56    ipv4         192.168.122.101/24\n"
    )

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(0, list_stdout),
            make_mock_process(0, dominfo_running),
            make_mock_process(0, domifaddr_stdout),
            make_mock_process(0, dominfo_stopped),
        ]
        
        vms = await provider.list_vms()
        
        assert len(vms) == 2
        assert vms[0].name == "my-running-vm"
        assert vms[0].status == VMStatus.RUNNING
        assert vms[0].cpu_count == 4
        assert vms[0].memory_mb == 4096
        assert vms[0].ip_address == "192.168.122.101"
        
        assert vms[1].name == "my-stopped-vm"
        assert vms[1].status == VMStatus.STOPPED
        assert vms[1].cpu_count == 2
        assert vms[1].memory_mb == 2048
        assert vms[1].ip_address is None

# makes sure we throw the right library error when virsh returns "domain not found".
@pytest.mark.asyncio
async def test_kvm_get_vm_info_not_found():
    provider = get_provider("kvm")
    stderr = b"error: failed to get domain 'missing-vm'\nerror: Domain not found: no domain with matching name 'missing-vm'"
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(1, b"", stderr)
        
        with pytest.raises(VMNotFoundError):
            await provider.get_vm_info("missing-vm")

# verifies start commands run successfully.
@pytest.mark.asyncio
async def test_kvm_start_vm():
    provider = get_provider("kvm")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"Domain my-vm started\n", b"")
        result = await provider.start_vm("my-vm")
        assert result is True

# check collision logic on double vm create attempts.
@pytest.mark.asyncio
async def test_kvm_create_vm_already_exists():
    provider = get_provider("kvm")
    dominfo_stdout = b"Name: test-vm\nState: running\nCPU(s): 1\nMax memory: 1024 kiB\n"
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, dominfo_stdout, b"")
        
        with pytest.raises(VMAlreadyExistsError):
            await provider.create_vm("test-vm", 1, 1024, "/path/to/disk.qcow2")

# verifies that create_vm on KVM formats the --cdrom command argument when iso_path is provided.
@pytest.mark.asyncio
async def test_kvm_create_vm_with_iso():
    provider = get_provider("kvm")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(1, b"", b"error: no domain with matching name test-vm"),
            make_mock_process(0, b"Domain created\n", b"")
        ]
        
        result = await provider.create_vm(
            name="test-vm",
            cpu_count=1,
            memory_mb=1024,
            disk_path="/path/to/disk.qcow2",
            iso_path="/path/to/boot.iso"
        )
        assert result is True
        
        args = mock_exec.call_args_list[1][0]
        assert "--cdrom" in args
        assert "/path/to/boot.iso" in args

# verifies that create_vm on KVM formats the cidata disk argument when cloud_init is provided.
@pytest.mark.asyncio
async def test_kvm_create_vm_with_cloud_init():
    provider = get_provider("kvm")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(1, b"", b"error: no domain with matching name test-vm"),
            make_mock_process(0, b"Domain created\n", b"")
        ]
        
        with patch("virtual_py.utils.cloudinit.create_cidata_iso") as mock_cidata:
            result = await provider.create_vm(
                name="test-vm",
                cpu_count=1,
                memory_mb=1024,
                disk_path="/path/to/disk.qcow2",
                cloud_init={
                    "hostname": "test-vm",
                    "username": "admin",
                    "password": "secretpassword",
                    "ssh_keys": ["ssh-rsa AAAAB3..."],
                    "shell_commands": ["echo boot > /tmp/boot"]
                }
            )
            assert result is True
            mock_cidata.assert_called_once()
            
            args = mock_exec.call_args_list[1][0]
            disk_arg_exists = any("test-vm-cidata.iso" in arg for arg in args)
            assert disk_arg_exists

# tests snapshot management functions mapping to virsh.
@pytest.mark.asyncio
async def test_kvm_checkpoints():
    provider = get_provider("kvm")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(0, b"Snapshot snap1 created\n"),
            make_mock_process(0, b"Snapshot snap1 reverted\n"),
            make_mock_process(0, b"Snapshot snap1 deleted\n"),
            make_mock_process(0, b"snap1\nsnap2\n"),
        ]
        
        assert await provider.create_checkpoint("my-vm", "snap1") is True
        assert await provider.restore_checkpoint("my-vm", "snap1") is True
        assert await provider.delete_checkpoint("my-vm", "snap1") is True
        
        snaps = await provider.list_checkpoints("my-vm")
        assert snaps == ["snap1", "snap2"]

# tests cpu/memory scaling.
@pytest.mark.asyncio
async def test_kvm_scaling():
    provider = get_provider("kvm")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"")
        
        assert await provider.set_vm_memory("my-vm", 2048, live=True) is True
        assert await provider.set_vm_cpus("my-vm", 4, live=True) is True

# check command execution with nested agent polling.
@pytest.mark.asyncio
async def test_kvm_execute_command():
    provider = get_provider("kvm")
    
    exec_res = json.dumps({"return": {"pid": 4567}}).encode()
    status_res = json.dumps({
        "return": {
            "exited": True,
            "exitcode": 0,
            "out-data": "aGVsbG8gZ3Vlc3Q=" # 'hello guest' base64
        }
    }).encode()
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(0, exec_res),
            make_mock_process(0, status_res),
        ]
        
        out = await provider.execute_command("my-vm", "echo hello guest")
        assert "hello guest" in out

# checks disk and network adapter hot-plugging CLI call translations.
@pytest.mark.asyncio
async def test_kvm_hotplug():
    provider = get_provider("kvm")
    
    # we simulate command inputs and responses dynamically to avoid strict ordering issues
    # when methods call get_vm_info or check status.
    async def mock_run_cmd(*args, **kwargs):
        cmd_str = " ".join(args)
        if "domblklist" in cmd_str:
            if not hasattr(mock_run_cmd, "called_blk"):
                mock_run_cmd.called_blk = True
                return make_mock_process(0, b"Target     Source\n------------------------------------------------\nvda        /path/to/my-vm.qcow2\n")
            return make_mock_process(0, b"Target     Source\n------------------------------------------------\nvda        /path/to/my-vm.qcow2\nvdb        /path/to/extra.qcow2\n")
        elif "dominfo" in cmd_str:
            return make_mock_process(0, b"Name: test-vm\nState: running\nCPU(s): 1\nMax memory: 1024 kiB\n")
        elif "domifaddr" in cmd_str:
            return make_mock_process(0, b" Name       MAC Address          Protocol     Address\n-------------------------------------------------------------------------\n vnet0      52:54:00:12:34:56    ipv4         192.168.122.101/24\n")
        elif "attach-disk" in cmd_str:
            return make_mock_process(0, b"Disk attached successfully\n")
        elif "detach-disk" in cmd_str:
            return make_mock_process(0, b"Disk detached successfully\n")
        elif "attach-interface" in cmd_str:
            return make_mock_process(0, b"Interface attached successfully\n")
        elif "detach-interface" in cmd_str:
            return make_mock_process(0, b"Interface detached successfully\n")
        return make_mock_process(0, b"")

    with patch("asyncio.create_subprocess_exec", side_effect=mock_run_cmd):
        assert await provider.attach_disk("test-vm", "/path/to/extra.qcow2") is True
        assert await provider.detach_disk("test-vm", "/path/to/extra.qcow2") is True
        
        mac = await provider.add_network_adapter("test-vm", "br0")
        assert mac.startswith("52:54:00:")
        
        assert await provider.remove_network_adapter("test-vm", mac) is True

# tests that the kvm provider rejects name and path injections with ValueError.
@pytest.mark.asyncio
async def test_kvm_security_validation():
    provider = get_provider("kvm")
    
    # test shell injection vm name.
    with pytest.raises(ValueError):
        await provider.start_vm("test-vm; rm -rf /")
        
    # test quote breakout checkpoint name.
    with pytest.raises(ValueError):
        await provider.create_checkpoint("test-vm", "snap'; reboot; '")
        
    # test redirection operators in disk path.
    with pytest.raises(ValueError):
        await provider.create_vm("test-vm", 1, 1024, "/var/lib/disk.qcow2 | touch /tmp/hacked")

# tests KVM create_vm with sysprep
@pytest.mark.asyncio
async def test_kvm_create_vm_with_sysprep():
    provider = get_provider("kvm")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(1, b"", b"error: no domain with matching name test-vm"),
            make_mock_process(0, b"Domain created\n", b"")
        ]
        
        with patch("virtual_py.utils.sysprep.create_unattend_iso") as mock_sysprep:
            result = await provider.create_vm(
                name="test-vm",
                cpu_count=1,
                memory_mb=1024,
                disk_path="/path/to/disk.qcow2",
                sysprep={
                    "hostname": "winhost",
                    "admin_password": "Pass!",
                    "raw_xml": "<unattend />"
                }
            )
            assert result is True
            expected_unattend_path = os.path.join(os.path.dirname(os.path.abspath("/path/to/disk.qcow2")), "test-vm-unattend.iso")
            mock_sysprep.assert_called_once_with(
                output_path=expected_unattend_path,
                hostname="winhost",
                admin_password="Pass!",
                raw_unattend_xml="<unattend />"
            )
            
            args = mock_exec.call_args_list[1][0]
            disk_arg_exists = any("test-vm-unattend.iso" in arg for arg in args)
            assert disk_arg_exists

@pytest.mark.asyncio
async def test_kvm_migrate():
    provider = get_provider("kvm")
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"Migration successful\n")
        assert await provider.migrate_vm("test-vm", "192.168.1.50") is True
        
        args = mock_exec.call_args[0]
        assert "migrate" in args
        assert "--live" in args
        assert "qemu+ssh://192.168.1.50/system" in args

    with pytest.raises(ValueError):
        await provider.migrate_vm("test-vm", "invalid; rm -rf /")


