import pytest
import sys
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from virtual_py.cli import run, handle_create, handle_list, handle_metrics
from virtual_py.core.exceptions import VMException
from virtual_py.core.models import VMInfo, VMStatus, VMMetrics

class DummyProvider:
    def __init__(self):
        self.list_vms = AsyncMock(return_value=[VMInfo("vm1", VMStatus.RUNNING, 1024, 2)])
        self.get_vm_info = AsyncMock(return_value=VMInfo("vm1", VMStatus.RUNNING, 1024, 2, "192.168.1.5"))
        self.start_vm = AsyncMock(return_value=True)
        self.stop_vm = AsyncMock(return_value=True)
        self.delete_vm = AsyncMock(return_value=True)
        self.create_vm = AsyncMock(return_value=True)
        self.set_vm_memory = AsyncMock(return_value=True)
        self.set_vm_cpus = AsyncMock(return_value=True)
        self.enable_secure_boot = AsyncMock(return_value=True)
        self.enable_nested_virtualization = AsyncMock(return_value=True)
        self.enable_tpm = AsyncMock(return_value=True)
        self.create_network = AsyncMock(return_value=True)
        self.delete_network = AsyncMock(return_value=True)
        self.list_networks = AsyncMock(return_value=["net1", "net2"])
        self.get_vm_metrics = AsyncMock(return_value=VMMetrics(5.5, 256, 120))
        self.migrate_vm = AsyncMock(return_value=True)
        self.clone_vm = AsyncMock(return_value=True)
        self.export_vm = AsyncMock(return_value=True)
        self.execute_command = AsyncMock(return_value="cmdoutput")
        self.copy_file_to_guest = AsyncMock(return_value=True)
        self.attach_disk = AsyncMock(return_value=True)
        self.detach_disk = AsyncMock(return_value=True)
        self.add_network_adapter = AsyncMock(return_value="00:11:22:33:44:55")
        self.remove_network_adapter = AsyncMock(return_value=True)

@pytest.mark.asyncio
async def test_cli_list_normal():
    provider = DummyProvider()
    args = MagicMock()
    args.json = False
    
    with patch("sys.stdout.write") as mock_write:
        await handle_list(args, provider)
        provider.list_vms.assert_called_once()

@pytest.mark.asyncio
async def test_cli_list_json():
    provider = DummyProvider()
    args = MagicMock()
    args.json = True
    
    with patch("builtins.print") as mock_print:
        await handle_list(args, provider)
        printed = mock_print.call_args[0][0]
        data = json.loads(printed)
        assert len(data) == 1
        assert data[0]["name"] == "vm1"

@pytest.mark.asyncio
async def test_cli_metrics():
    provider = DummyProvider()
    args = MagicMock()
    args.name = "vm1"
    args.json = False
    
    with patch("builtins.print") as mock_print:
        await handle_metrics(args, provider)
        provider.get_vm_metrics.assert_called_once_with("vm1")
        assert any("CPU Usage" in call[0][0] for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_cli_create_raw_user_data_missing(tmp_path):
    args = MagicMock()
    args.raw_user_data = str(tmp_path / "nonexistent")
    args.cloud_init = None
    args.sysprep = None
    provider = DummyProvider()
    
    with patch("sys.exit", side_effect=SystemExit) as mock_exit:
        with pytest.raises(SystemExit):
            await handle_create(args, provider)
        mock_exit.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_cli_create_with_raw_user_data(tmp_path):
    user_data_file = tmp_path / "user_data.yaml"
    user_data_file.write_text("#cloud-config\nhostname: test")
    
    args = MagicMock()
    args.name = "testvm"
    args.os = None
    args.disk = "/fake/disk.qcow2"
    args.ram = 2048
    args.cpu = 4
    args.network = "net1"
    args.iso = "/fake/iso"
    args.raw_user_data = str(user_data_file)
    args.cloud_init = None
    args.sysprep = None
    
    provider = DummyProvider()
    with patch("builtins.print"):
        await handle_create(args, provider)
        provider.create_vm.assert_called_once_with(
            name="testvm",
            cpu_count=4,
            memory_mb=2048,
            disk_path="/fake/disk.qcow2",
            network_name="net1",
            iso_path="/fake/iso",
            cloud_init=None,
            raw_user_data="#cloud-config\nhostname: test",
            sysprep=None
        )

@pytest.mark.asyncio
async def test_cli_dispatch_list():
    provider = DummyProvider()
    test_args = ["cli.py", "list"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("virtual_py.cli.handle_list") as mock_handle:
        
        # We run the cli main
        await run()
        mock_handle.assert_called_once()

@pytest.mark.asyncio
async def test_cli_migrate():
    provider = DummyProvider()
    test_args = ["cli.py", "migrate", "vm1", "10.0.0.99"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("builtins.print") as mock_print:
         
        await run()
        provider.migrate_vm.assert_called_once_with("vm1", "10.0.0.99")
        mock_print.assert_any_call("vm 'vm1' migrated successfully.")

@pytest.mark.asyncio
async def test_cli_clone():
    provider = DummyProvider()
    test_args = ["cli.py", "clone", "vm1", "vm1-clone"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("builtins.print") as mock_print:
        await run()
        provider.clone_vm.assert_called_once_with("vm1", "vm1-clone")

@pytest.mark.asyncio
async def test_cli_export():
    provider = DummyProvider()
    test_args = ["cli.py", "export", "vm1", "/tmp/export"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("builtins.print") as mock_print:
        await run()
        provider.export_vm.assert_called_once_with("vm1", "/tmp/export")

@pytest.mark.asyncio
async def test_cli_execute():
    provider = DummyProvider()
    test_args = ["cli.py", "execute", "vm1", "ls -la", "--username", "root", "--password", "secret"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("sys.stdout.write") as mock_stdout:
        await run()
        provider.execute_command.assert_called_once_with("vm1", "ls -la", username="root", password="secret")
        mock_stdout.assert_any_call("cmdoutput")

@pytest.mark.asyncio
async def test_cli_copy():
    provider = DummyProvider()
    test_args = ["cli.py", "copy", "vm1", "/local/path", "/guest/path"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("builtins.print") as mock_print:
        await run()
        provider.copy_file_to_guest.assert_called_once_with("vm1", "/local/path", "/guest/path", username=None, password=None)

@pytest.mark.asyncio
async def test_cli_device():
    provider = DummyProvider()
    
    # attach disk
    test_args = ["cli.py", "device", "attach-disk", "vm1", "--disk-path", "/fake/disk"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("builtins.print"):
        await run()
        provider.attach_disk.assert_called_once_with("vm1", "/fake/disk", controller_type=None)

    # attach nic
    test_args2 = ["cli.py", "device", "attach-nic", "vm1", "--switch-name", "switch1"]
    with patch("sys.argv", test_args2), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("builtins.print") as mock_print:
        await run()
        provider.add_network_adapter.assert_called_once_with("vm1", "switch1")
        mock_print.assert_any_call("nic attached successfully. mac address: 00:11:22:33:44:55")

@pytest.mark.asyncio
async def test_cli_iac(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("networks:\n  - name: net1\nvms:\n  - name: vm1\n    cpu: 2\n    ram: 2048\n    disk: /path")
    
    test_args = ["cli.py", "iac", "apply", "-f", str(yaml_file)]
    with patch("sys.argv", test_args), \
         patch("virtual_py.iac.get_provider") as mock_get_provider, \
         patch("builtins.print"):
        mock_prov = mock_get_provider.return_value
        mock_prov.list_networks = AsyncMock(return_value=[])
        mock_prov.create_network = AsyncMock(return_value=True)
        mock_prov.get_vm_info = AsyncMock(side_effect=Exception("not found"))
        mock_prov.create_vm = AsyncMock(return_value=True)
        await run()
        mock_prov.create_network.assert_called_once_with("net1", "192.168.100.0/24")
        mock_prov.create_vm.assert_called_once()

@pytest.mark.asyncio
async def test_cli_backup():
    provider = DummyProvider()
    test_args = ["cli.py", "backup", "vm1", "/tmp/backup.tar.gz"]
    with patch("sys.argv", test_args), \
         patch("virtual_py.cli.get_provider", return_value=provider), \
         patch("virtual_py.utils.backup.create_backup", new_callable=AsyncMock) as mock_backup, \
         patch("builtins.print"):
        await run()
        mock_backup.assert_called_once_with("vm1", "/tmp/backup.tar.gz")


