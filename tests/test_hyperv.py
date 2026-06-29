import pytest
import json
from unittest.mock import AsyncMock, patch
from virtual_py import get_provider
from virtual_py.core.exceptions import VMNotFoundError, VMAlreadyExistsError, HypervisorExecutionError
from virtual_py.core.models import VMStatus

def make_mock_process(returncode=0, stdout=b"", stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, stderr)
    return proc

@pytest.mark.asyncio
async def test_hyperv_list_vms_multiple():
    provider = get_provider("hyperv")
    
    mock_json = [
        {"Name": "vm1", "State": "Running", "MemoryMB": 2048, "CPUCount": 2, "IPAddress": "192.168.1.100"},
        {"Name": "vm2", "State": "Off", "MemoryMB": 1024, "CPUCount": 1, "IPAddress": None}
    ]
    stdout = json.dumps(mock_json).encode()
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, stdout, b"")
        
        vms = await provider.list_vms()
        assert len(vms) == 2
        assert vms[0].name == "vm1"
        assert vms[0].status == VMStatus.RUNNING
        assert vms[0].memory_mb == 2048
        assert vms[0].cpu_count == 2
        assert vms[0].ip_address == "192.168.1.100"
        
        assert vms[1].name == "vm2"
        assert vms[1].status == VMStatus.STOPPED
        assert vms[1].memory_mb == 1024
        assert vms[1].cpu_count == 1
        assert vms[1].ip_address is None

# checks list parser works when only a single VM dictionary is returned instead of a list.
# powershell ConvertTo-Json converts collections of size 1 into a flat dictionary, which can break client logic.
@pytest.mark.asyncio
async def test_hyperv_list_vms_single():
    provider = get_provider("hyperv")
    
    mock_json = {"Name": "vm1", "State": "Running", "MemoryMB": 2048, "CPUCount": 2, "IPAddress": "192.168.1.100"}
    stdout = json.dumps(mock_json).encode()
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, stdout, b"")
        
        vms = await provider.list_vms()
        assert len(vms) == 1
        assert vms[0].name == "vm1"
        assert vms[0].status == VMStatus.RUNNING
        assert vms[0].ip_address == "192.168.1.100"

# exit code 10 is our custom error mapping for non-existent VMs in Get-VM queries.
@pytest.mark.asyncio
async def test_hyperv_get_vm_info_not_found():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(10, b"", b"vm not found")
        
        with pytest.raises(VMNotFoundError):
            await provider.get_vm_info("missing-vm")

# verifies start commands call powershell correctly.
@pytest.mark.asyncio
async def test_hyperv_start_vm():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"", b"")
        result = await provider.start_vm("test-vm")
        assert result is True

# verifies that create_vm on Hyper-V runs the New-VM PowerShell script.
@pytest.mark.asyncio
async def test_hyperv_create_vm():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(10, b"", b"vm not found"),
            make_mock_process(0, b"", b"")
        ]
        
        result = await provider.create_vm(
            name="test-vm",
            cpu_count=2,
            memory_mb=2048,
            disk_path="C:\\VMs\\test.vhdx"
        )
        assert result is True
        
        script = mock_exec.call_args_list[1][0][4]
        assert "New-VM" in script
        assert "Set-VMProcessor" in script
        assert "Add-VMDvdDrive" not in script

# verifies that create_vm on Hyper-V attaches DVD and sets UEFI firmware when iso_path is provided.
@pytest.mark.asyncio
async def test_hyperv_create_vm_with_iso():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(10, b"", b"vm not found"),
            make_mock_process(0, b"", b"")
        ]
        
        result = await provider.create_vm(
            name="test-vm",
            cpu_count=2,
            memory_mb=2048,
            disk_path="C:\\VMs\\test.vhdx",
            iso_path="C:\\VMs\\boot.iso"
        )
        assert result is True
        
        script = mock_exec.call_args_list[1][0][4]
        assert "Add-VMDvdDrive" in script
        assert "Set-VMFirmware" in script
        assert "boot.iso" in script

# verifies that create_vm on Hyper-V attaches cidata DVD when cloud_init is provided.
@pytest.mark.asyncio
async def test_hyperv_create_vm_with_cloud_init():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(10, b"", b"vm not found"),
            make_mock_process(0, b"", b"")
        ]
        
        with patch("virtual_py.utils.cloudinit.create_cidata_iso") as mock_cidata:
            result = await provider.create_vm(
                name="test-vm",
                cpu_count=2,
                memory_mb=2048,
                disk_path="C:\\VMs\\test.vhdx",
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
            
            script = mock_exec.call_args_list[1][0][4]
            assert "Add-VMDvdDrive" in script
            assert "test-vm-cidata.iso" in script

# checkpoint commands.
@pytest.mark.asyncio
async def test_hyperv_checkpoints():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(0, b""),
            make_mock_process(0, b""),
            make_mock_process(0, b""),
            make_mock_process(0, b'["snap1", "snap2"]')
        ]
        
        assert await provider.create_checkpoint("vm1", "snap1") is True
        assert await provider.restore_checkpoint("vm1", "snap1") is True
        assert await provider.delete_checkpoint("vm1", "snap1") is True
        
        snaps = await provider.list_checkpoints("vm1")
        assert snaps == ["snap1", "snap2"]

# core resource scaling.
@pytest.mark.asyncio
async def test_hyperv_scaling():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"")
        
        assert await provider.set_vm_memory("vm1", 4096, live=True) is True
        assert await provider.set_vm_cpus("vm1", 4) is True

# guest commands via powershell direct.
@pytest.mark.asyncio
async def test_hyperv_execute_command():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"command output string\n")
        
        out = await provider.execute_command("vm1", "hostname", "admin", "secret")
        assert "command output string" in out

# checks disk and network adapter hot-plugging cmdlet execution wrappers.
@pytest.mark.asyncio
async def test_hyperv_hotplug():
    provider = get_provider("hyperv")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = [
            make_mock_process(0, b""),  # attach_disk
            make_mock_process(0, b""),  # detach_disk
            make_mock_process(0, b"00155D000102\n"),  # add_network_adapter
            make_mock_process(0, b""),  # remove_network_adapter
        ]
        
        assert await provider.attach_disk("vm1", "C:\\VMs\\extra.vhdx") is True
        assert await provider.detach_disk("vm1", "C:\\VMs\\extra.vhdx") is True
        
        mac = await provider.add_network_adapter("vm1", "Default Switch")
        assert mac == "00155D000102"
        
        assert await provider.remove_network_adapter("vm1", mac) is True

# tests that the hyper-v provider rejects name and path injections with ValueError.
@pytest.mark.asyncio
async def test_hyperv_security_validation():
    provider = get_provider("hyperv")
    
    # test shell injection vm name.
    with pytest.raises(ValueError):
        await provider.start_vm("test-vm; Stop-Process -Name lsass")
        
    # test quote breakout checkpoint name.
    with pytest.raises(ValueError):
        await provider.create_checkpoint("test-vm", "snap'; reboot; '")
        
    # test redirection operators in disk path.
    with pytest.raises(ValueError):
        await provider.create_vm("test-vm", 1, 1024, "C:\\VMs\\disk.vhdx & format C:")

@pytest.mark.asyncio
async def test_hyperv_migrate():
    provider = get_provider("hyperv")
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = make_mock_process(0, b"Migration successful\n")
        assert await provider.migrate_vm("test-vm", "192.168.1.50") is True
        
        args = mock_exec.call_args[0]
        # PowerShell command string is inside args
        powershell_cmd = args[-1]
        assert "Move-VM" in powershell_cmd
        assert "DestinationHost '192.168.1.50'" in powershell_cmd

    with pytest.raises(ValueError):
        await provider.migrate_vm("test-vm", "invalid; Stop-Process -Name lsass")

