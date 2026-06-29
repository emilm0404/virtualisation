import asyncio
import json
import os
import sys
import re
from typing import List, Optional
from virtual_py.core.interfaces import VMProvider
from virtual_py.core.models import VMInfo, VMStatus
from virtual_py.utils.validation import (
    validate_vm_name,
    validate_checkpoint_name,
    validate_path,
)
from virtual_py.core.exceptions import (
    VMNotFoundError,
    VMAlreadyExistsError,
    HypervisorExecutionError,
)

class HyperVProvider(VMProvider):

    def __init__(self, powershell_path: str = "powershell.exe"):
        self.powershell_path = powershell_path

    async def _run_powershell(self, script: str) -> str:
        cmd = [
            self.powershell_path,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
        except Exception as e:
            raise HypervisorExecutionError(
                command=script,
                returncode=-1,
                stdout="",
                stderr=str(e),
                message=f"failed to run powershell command because: {str(e)}"
            )

        if proc.returncode != 0:
            raise HypervisorExecutionError(
                command=script,
                returncode=proc.returncode,
                stdout=stdout.decode(errors="replace").strip(),
                stderr=stderr.decode(errors="replace").strip()
            )
        return stdout.decode(errors="replace").strip()

    # state mapping for hyper-v enums.
    def _map_state(self, state) -> str:
        state_str = str(state).lower()
        if "running" in state_str:
            return VMStatus.RUNNING
        elif "off" in state_str:
            return VMStatus.STOPPED
        elif "paused" in state_str:
            return VMStatus.PAUSED
        return VMStatus.UNKNOWN

    async def create_vm(
        self,
        name: str,
        cpu_count: int,
        memory_mb: int,
        disk_path: str,
        network_name: Optional[str] = None,
        iso_path: Optional[str] = None,
        cloud_init: Optional[dict] = None,
        raw_user_data: Optional[str] = None,
        sysprep: Optional[dict] = None,
        **kwargs
    ) -> bool:
        validate_vm_name(name)
        validate_path(disk_path)
        if network_name:
            validate_vm_name(network_name)
        if iso_path:
            validate_path(iso_path)

        try:
            await self.get_vm_info(name)
            raise VMAlreadyExistsError(name)
        except VMNotFoundError:
            pass

        abs_disk_path = os.path.abspath(disk_path)
        disk_dir = os.path.dirname(abs_disk_path)
        
        # escape single quotes for powershell string literals.
        esc_disk_path = abs_disk_path.replace("'", "''")
        esc_disk_dir = disk_dir.replace("'", "''")
        
        net_part = f"-SwitchName '{network_name}'" if network_name else ""
        
        # build and mount seed ISO for automatic cloud-init setup.
        cidata_cmd = ""
        if cloud_init or raw_user_data:
            from virtual_py.utils.cloudinit import create_cidata_iso
            cidata_path = os.path.join(disk_dir, f"{name}-cidata.iso")
            
            c_hostname = cloud_init.get("hostname", name) if cloud_init else name
            c_user = cloud_init.get("username", "admin") if cloud_init else "admin"
            c_pass = cloud_init.get("password") if cloud_init else None
            c_ssh = cloud_init.get("ssh_keys") if cloud_init else None
            c_cmd = cloud_init.get("shell_commands") if cloud_init else None
            
            create_cidata_iso(
                output_path=cidata_path,
                hostname=c_hostname,
                username=c_user,
                password=c_pass,
                ssh_keys=c_ssh,
                shell_commands=c_cmd,
                raw_user_data=raw_user_data
            )
            esc_cidata_path = cidata_path.replace("'", "''")
            cidata_cmd += f"\nAdd-VMDvdDrive -VMName '{name}' -Path '{esc_cidata_path}' | Out-Null"
            
        if sysprep:
            from virtual_py.utils.sysprep import create_unattend_iso
            unattend_path = os.path.join(disk_dir, f"{name}-unattend.iso")
            create_unattend_iso(
                output_path=unattend_path,
                hostname=sysprep.get("hostname", name),
                admin_password=sysprep.get("admin_password", "Password123!"),
                raw_unattend_xml=sysprep.get("raw_xml")
            )
            esc_unattend = unattend_path.replace("'", "''")
            cidata_cmd += f"\nAdd-VMDvdDrive -VMName '{name}' -Path '{esc_unattend}' | Out-Null"
        
        # dynamic script content depending on iso presence.
        iso_cmd = ""
        if iso_path:
            abs_iso_path = os.path.abspath(iso_path)
            esc_iso_path = abs_iso_path.replace("'", "''")
            iso_name_esc = os.path.basename(abs_iso_path).replace("'", "''")
            # if iso is specified, we attach dvd, disable secure boot, and boot from dvd first.
            iso_cmd = f"""
            Add-VMDvdDrive -VMName '{name}' -Path '{esc_iso_path}' | Out-Null
            Set-VMFirmware -VMName '{name}' -EnableSecureBoot Off | Out-Null
            $dvd = Get-VMDvdDrive -VMName '{name}' | Where-Object {{ $_.Path -like '*{iso_name_esc}*' }} | Select-Object -First 1
            Set-VMFirmware -VMName '{name}' -FirstBootDevice $dvd | Out-Null
            """
        
        # New-VHD dynamically allocates space so it is very fast to start.
        script = f"""
        $ErrorActionPreference = 'Stop'
        if (-not (Test-Path '{esc_disk_dir}')) {{
            New-Item -ItemType Directory -Path '{esc_disk_dir}' -Force | Out-Null
        }}
        if (-not (Test-Path '{esc_disk_path}')) {{
            New-VHD -Path '{esc_disk_path}' -SizeBytes 20GB -Dynamic | Out-Null
        }}
        New-VM -Name '{name}' -MemoryStartupBytes ({memory_mb} * 1MB) -VHDPath '{esc_disk_path}' -Generation 2 {net_part} | Out-Null
        Set-VMProcessor -VMName '{name}' -Count {cpu_count} | Out-Null
        {iso_cmd}
        {cidata_cmd}
        """
        
        try:
            await self._run_powershell(script)
            return True
        except HypervisorExecutionError as e:
            raise HypervisorExecutionError(
                command=e.command,
                returncode=e.returncode,
                stdout=e.stdout,
                stderr=e.stderr,
                message=f"failed to create vm '{name}': {e.stderr}"
            )

    # powers on the VM.
    async def start_vm(self, name: str) -> bool:
        validate_vm_name(name)
        script = f"Start-VM -Name '{name}'"
        try:
            await self._run_powershell(script)
            return True
        except HypervisorExecutionError as e:
            if "not find a virtual machine" in e.stderr:
                raise VMNotFoundError(name)
            raise

    # stops the VM. TurnOff does a hard shutoff (pulling the plug).
    async def stop_vm(self, name: str, force: bool = False) -> bool:
        validate_vm_name(name)
        stop_arg = "-TurnOff" if force else ""
        script = f"Stop-VM -Name '{name}' {stop_arg}"
        try:
            await self._run_powershell(script)
            return True
        except HypervisorExecutionError as e:
            if "not find a virtual machine" in e.stderr:
                raise VMNotFoundError(name)
            raise

    # removes VM configuration and deletes virtual disk files.
    # warning: Remove-VM only deletes hyper-v config, we have to clean the vhdx manually.
    async def delete_vm(self, name: str) -> bool:
        validate_vm_name(name)
        script = f"""
        $ErrorActionPreference = 'Stop'
        $vm = Get-VM -Name '{name}' -ErrorAction SilentlyContinue
        if (-not $vm) {{
            throw "vm not found"
        }}
        $paths = $vm.HardDrives.Path
        Remove-VM -Name '{name}' -Force
        foreach ($path in $paths) {{
            if (Test-Path $path) {{
                Remove-Item -Path $path -Force
            }}
        }}
        """
        try:
            await self._run_powershell(script)
            return True
        except HypervisorExecutionError as e:
            if "vm not found" in e.stderr or "not find a virtual machine" in e.stderr:
                raise VMNotFoundError(name)
            raise

    # fetches info for a single VM.
    # ConvertTo-Json yields string output that we deserialize in Python.
    # ugh, powershell lists state as an int if convertto-json runs on enum directly, so force string representation.
    # gets guest network adapter details to report the first IPv4 address.
    async def get_vm_info(self, name: str) -> VMInfo:
        validate_vm_name(name)
        script = f"""
        $vm = Get-VM -Name '{name}' -ErrorAction SilentlyContinue
        if (-not $vm) {{
            exit 10
        }}
        $ipAddresses = Get-VMNetworkAdapter -VMName '{name}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddresses
        $ip = $ipAddresses | Where-Object {{ $_ -like '*.*' }} | Select-Object -First 1
        $vm | Select-Object Name, @{{Name='State';Expression={{$_.State.ToString()}}}}, @{{Name='MemoryMB';Expression={{[int]($_.MemoryStartup / 1MB)}}}}, @{{Name='CPUCount';Expression={{$_.ProcessorCount}}}}, @{{Name='IPAddress';Expression={{$ip}}}} | ConvertTo-Json -Compress
        """
        try:
            stdout = await self._run_powershell(script)
        except HypervisorExecutionError as e:
            if e.returncode == 10:
                raise VMNotFoundError(name)
            raise

        if not stdout:
            raise VMNotFoundError(name)

        try:
            data = json.loads(stdout)
            ip_val = data.get("IPAddress")
            if isinstance(ip_val, dict) and not ip_val:
                ip_val = None
            return VMInfo(
                name=data["Name"],
                status=self._map_state(data["State"]),
                memory_mb=data["MemoryMB"],
                cpu_count=data["CPUCount"],
                ip_address=ip_val
            )
        except Exception as e:
            raise HypervisorExecutionError(
                command=script,
                returncode=0,
                stdout=stdout,
                stderr=str(e),
                message=f"failed to parse powershell json: {str(e)}"
            )

    # returns list of all virtual machines.
    # converts single object or arrays gracefully to standard python dicts.
    async def list_vms(self) -> List[VMInfo]:
        script = """
        $vms = @(Get-VM)
        if ($vms.Count -gt 0) {
            $vms | Select-Object Name, @{Name='State';Expression={$_.State.ToString()}}, @{Name='MemoryMB';Expression={[int]($_.MemoryStartup / 1MB)}}, @{Name='CPUCount';Expression={$_.ProcessorCount}}, @{Name='IPAddress';Expression={
                ((Get-VMNetworkAdapter -VMName $_.Name -ErrorAction SilentlyContinue).IPAddresses | Where-Object { $_ -like '*.*' } | Select-Object -First 1)
            }} | ConvertTo-Json -Compress
        } else {
            "[]"
        }
        """
        stdout = await self._run_powershell(script)
        if not stdout or stdout.strip() == "[]":
            return []

        try:
            data = json.loads(stdout)
            if not isinstance(data, list):
                data = [data]
            
            vms = []
            for item in data:
                ip_val = item.get("IPAddress")
                if isinstance(ip_val, dict) and not ip_val:
                    ip_val = None
                vms.append(VMInfo(
                    name=item["Name"],
                    status=self._map_state(item["State"]),
                    memory_mb=item["MemoryMB"],
                    cpu_count=item["CPUCount"],
                    ip_address=ip_val
                ))
            return vms
        except Exception as e:
            raise HypervisorExecutionError(
                command=script,
                returncode=0,
                stdout=stdout,
                stderr=str(e),
                message=f"failed to parse list of vms from json: {str(e)}"
            )

    # checkpoint commands.
    async def create_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_checkpoint_name(checkpoint_name)
        script = f"Checkpoint-VM -Name '{vm_name}' -SnapshotName '{checkpoint_name}'"
        await self._run_powershell(script)
        return True

    # rolls back the virtual machine configuration state.
    # Confirm:$false skips user prompt blockages.
    async def restore_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_checkpoint_name(checkpoint_name)
        script = f"Restore-VMCheckpoint -VMName '{vm_name}' -Name '{checkpoint_name}' -Confirm:$false"
        await self._run_powershell(script)
        return True

    # deletes snapshots. merges standard disk states.
    async def delete_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_checkpoint_name(checkpoint_name)
        script = f"Remove-VMCheckpoint -VMName '{vm_name}' -Name '{checkpoint_name}'"
        await self._run_powershell(script)
        return True

    # lists snapshot tree nodes.
    async def list_checkpoints(self, vm_name: str) -> List[str]:
        validate_vm_name(vm_name)
        script = f"""
        $checkpoints = @(Get-VMCheckpoint -VMName '{vm_name}')
        if ($checkpoints) {{
            $checkpoints | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress
        }} else {{
            "[]"
        }}
        """
        stdout = await self._run_powershell(script)
        if not stdout or stdout.strip() == "[]":
            return []
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return data
            return [data]
        except Exception:
            return []

    # runs script commands inside the vm guest operating system.
    # hyper-v power shell direct utilizes internal vmbus integration.
    # guest credentials must be supplied to authenticate.
    async def execute_command(
        self,
        vm_name: str,
        command: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> str:
        validate_vm_name(vm_name)
        if not username or not password:
            raise ValueError("hyper-v powershell direct guest command execution requires guest credentials.")
            
        esc_username = username.replace("'", "''")
        esc_password = password.replace("'", "''")
        
        script = f"""
        $secpasswd = ConvertTo-SecureString '{esc_password}' -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential ('{esc_username}', $secpasswd)
        $res = Invoke-Command -VMName '{vm_name}' -Credential $cred -ScriptBlock {{ {command} }} -ErrorAction Stop
        $res | Out-String
        """
        return await self._run_powershell(script)

    # transfers a local host file to guest path.
    # Copy-VMFile requires File Source host flag.
    async def copy_file_to_guest(
        self,
        vm_name: str,
        host_path: str,
        guest_path: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> bool:
        validate_vm_name(vm_name)
        validate_path(host_path)
        validate_path(guest_path)
        
        if not username or not password:
            raise ValueError("hyper-v Copy-VMFile requires guest credentials.")
            
        abs_host_path = os.path.abspath(host_path)
        esc_host_path = abs_host_path.replace("'", "''")
        esc_guest_path = guest_path.replace("'", "''")
        esc_username = username.replace("'", "''")
        esc_password = password.replace("'", "''")
        
        script = f"""
        $secpasswd = ConvertTo-SecureString '{esc_password}' -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential ('{esc_username}', $secpasswd)
        Copy-VMFile -Name '{vm_name}' -SourcePath '{esc_host_path}' -DestinationPath '{esc_guest_path}' -CreateFolder -FileSource Host -Credential $cred -ErrorAction Stop
        """
        await self._run_powershell(script)
        return True

    # adjusts memory allocation.
    # handles running vms by modifying active dynamic limits safely.
    async def set_vm_memory(self, vm_name: str, memory_mb: int, live: bool = False) -> bool:
        validate_vm_name(vm_name)
        script = f"""
        $vm = Get-VM -Name '{vm_name}' -ErrorAction Stop
        if ($vm.State -eq 'Running') {{
            if ('{live}' -eq 'True') {{
                $bytes = {memory_mb} * 1MB
                if ($bytes -gt $vm.MemoryMaximum) {{
                    Set-VMMemory -VMName '{vm_name}' -MaximumBytes $bytes -ErrorAction Stop
                }}
                if ($bytes -le $vm.MemoryStartup) {{
                    Set-VMMemory -VMName '{vm_name}' -MinimumBytes $bytes -ErrorAction Stop
                }}
            }} else {{
                throw "cannot scale startup memory on running vm without live set to true"
            }}
        }} else {{
            Set-VMMemory -VMName '{vm_name}' -StartupBytes ({memory_mb} * 1MB) -ErrorAction Stop
        }}
        """
        await self._run_powershell(script)
        return True

    # hot-plug vcpus.
    # hyper-v doesn't support live cpu plug, raises error if vm is running.
    async def set_vm_cpus(self, vm_name: str, cpu_count: int, live: bool = False) -> bool:
        validate_vm_name(vm_name)
        script = f"""
        $vm = Get-VM -Name '{vm_name}' -ErrorAction Stop
        if ($vm.State -eq 'Running') {{
            throw "hyper-v does not support hot-plugging CPU cores on active VMs"
        }}
        Set-VMProcessor -VMName '{vm_name}' -Count {cpu_count} -ErrorAction Stop
        """
        await self._run_powershell(script)
        return True

    # attaches a secondary hard disk to SCSI controller 0.
    # automatically searches for the first available SCSI controller slot location (0-63).
    async def attach_disk(self, vm_name: str, disk_path: str, controller_type: Optional[str] = None) -> bool:
        validate_vm_name(vm_name)
        validate_path(disk_path)
        
        abs_disk_path = os.path.abspath(disk_path)
        esc_disk_path = abs_disk_path.replace("'", "''")
        
        script = f"""
        $ErrorActionPreference = 'Stop'
        $drives = Get-VMHardDiskDrive -VMName '{vm_name}' | Where-Object {{ $_.ControllerType -eq 'SCSI' -and $_.ControllerNumber -eq 0 }}
        $used = $drives | Select-Object -ExpandProperty ControllerLocation
        $free = 0..63 | Where-Object {{ $_ -notin $used }} | Select-Object -First 1
        if ($free -eq $null) {{
            throw "no available slots on SCSI controller 0 for VM '{vm_name}'."
        }}
        Add-VMHardDiskDrive -VMName '{vm_name}' -Path '{esc_disk_path}' -ControllerNumber 0 -ControllerLocation $free
        """
        await self._run_powershell(script)
        return True

    # removes secondary hard disk from vm configurations.
    async def detach_disk(self, vm_name: str, disk_path: str) -> bool:
        validate_vm_name(vm_name)
        validate_path(disk_path)
        
        abs_disk_path = os.path.abspath(disk_path)
        esc_disk_path = abs_disk_path.replace("'", "''")
        
        script = f"Remove-VMHardDiskDrive -VMName '{vm_name}' -Path '{esc_disk_path}' -ErrorAction Stop"
        await self._run_powershell(script)
        return True

    # adds network card to dynamic switch and returns the mac.
    async def add_network_adapter(self, vm_name: str, switch_name: str) -> str:
        validate_vm_name(vm_name)
        validate_vm_name(switch_name)
        
        script = f"""
        $ErrorActionPreference = 'Stop'
        $nic = Add-VMNetworkAdapter -VMName '{vm_name}' -SwitchName '{switch_name}' -Passthru
        $nic.MacAddress
        """
        return await self._run_powershell(script)

    # detaches interface based on unique MAC.
    async def remove_network_adapter(self, vm_name: str, adapter_mac: str) -> bool:
        validate_vm_name(vm_name)
        if not re.match(r"^[0-9a-fA-F:-]+$", adapter_mac):
            raise ValueError(f"invalid MAC address format: '{adapter_mac}'")
            
        script = f"""
        $ErrorActionPreference = 'Stop'
        $nic = Get-VMNetworkAdapter -VMName '{vm_name}' | Where-Object {{ $_.MacAddress -eq '{adapter_mac}' }}
        if (-not $nic) {{
            throw "network adapter with MAC '{adapter_mac}' not found."
        }}
        Remove-VMNetworkAdapter -VMNetworkAdapter $nic
        """
        await self._run_powershell(script)
        return True

    # --- Advanced Configuration ---
    async def enable_secure_boot(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        state = "On" if enabled else "Off"
        script = f"Set-VMFirmware -VMName '{vm_name}' -EnableSecureBoot {state}"
        await self._run_powershell(script)
        return True

    async def enable_nested_virtualization(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        state = "$true" if enabled else "$false"
        script = f"Set-VMProcessor -VMName '{vm_name}' -ExposeVirtualizationExtensions {state}"
        await self._run_powershell(script)
        return True

    async def enable_tpm(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        if enabled:
            # Enable Key Protector and vTPM
            script = f"""
            $ErrorActionPreference = 'Stop'
            $vm = Get-VM -Name '{vm_name}'
            $owner = Get-HgsGuardian UntrustedGuardian
            $kp = New-HgsKeyProtector -Owner $owner -AllowUntrustedRoot
            Set-VMKeyProtector -VMName '{vm_name}' -KeyProtector $kp.RawData
            Enable-VMTPM -VMName '{vm_name}'
            """
        else:
            script = f"Disable-VMTPM -VMName '{vm_name}'"
        await self._run_powershell(script)
        return True

    # --- Virtual Network Management ---
    async def create_network(self, name: str, subnet_cidr: str) -> bool:
        validate_vm_name(name)
        # In Hyper-V, we create an internal switch.
        # NAT routing requires New-NetNat, which is more complex, but we'll create the internal switch.
        script = f"""
        $ErrorActionPreference = 'Stop'
        $switch = Get-VMSwitch -Name '{name}' -ErrorAction SilentlyContinue
        if (-not $switch) {{
            New-VMSwitch -Name '{name}' -SwitchType Internal
        }}
        """
        await self._run_powershell(script)
        return True

    async def delete_network(self, name: str) -> bool:
        validate_vm_name(name)
        script = f"Remove-VMSwitch -Name '{name}' -Force"
        await self._run_powershell(script)
        return True

    async def list_networks(self) -> List[str]:
        script = """
        $switches = @(Get-VMSwitch)
        if ($switches) {
            $switches | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress
        } else {
            "[]"
        }
        """
        stdout = await self._run_powershell(script)
        if not stdout or stdout.strip() == "[]":
            return []
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return data
            return [data]
        except Exception:
            return []

    # --- Telemetry & Metrics ---
    async def get_vm_metrics(self, vm_name: str) -> "VMMetrics":
        from virtual_py.core.models import VMMetrics
        validate_vm_name(vm_name)
        script = f"""
        $ErrorActionPreference = 'Stop'
        $vm = Get-VM -Name '{vm_name}'
        $vm | Select-Object CPUUsage, @{{Name='MemoryDemand';Expression={{[int]($_.MemoryDemand / 1MB)}}}}, Uptime | ConvertTo-Json -Compress
        """
        try:
            stdout = await self._run_powershell(script)
            data = json.loads(stdout)
            
            uptime_str = data.get("Uptime", {}).get("TotalSeconds", 0)
            if isinstance(data.get("Uptime"), str):
                # TimeSpan string parsing if PS outputs string
                uptime_str = 0 # simplified
            elif isinstance(data.get("Uptime"), dict):
                uptime_str = data["Uptime"].get("TotalSeconds", 0)
                
            return VMMetrics(
                cpu_usage_percent=float(data.get("CPUUsage", 0)),
                memory_demand_mb=int(data.get("MemoryDemand", 0)),
                uptime_seconds=int(uptime_str)
            )
        except Exception as e:
            return VMMetrics(0.0, 0, 0)

    async def migrate_vm(self, vm_name: str, target_host: str, **kwargs) -> bool:
        validate_vm_name(vm_name)
        if not re.match(r"^[a-zA-Z0-9.-]+$", target_host):
            raise ValueError(f"invalid target host address: '{target_host}'")
        
        script = f"Move-VM -Name '{vm_name}' -DestinationHost '{target_host}' -ErrorAction Stop"
        await self._run_powershell(script)
        return True

    async def create_storage_pool(self, name: str, path: str) -> bool:
        validate_vm_name(name)
        validate_path(path)
        esc_path = path.replace("'", "''")
        script = f"""
        $ErrorActionPreference = 'Stop'
        if (-not (Test-Path '{esc_path}')) {{
            New-Item -ItemType Directory -Path '{esc_path}' -Force | Out-Null
        }}
        Set-VMHost -VirtualHardDiskPath '{esc_path}' -ErrorAction SilentlyContinue
        """
        await self._run_powershell(script)
        return True

    async def delete_storage_pool(self, name: str) -> bool:
        validate_vm_name(name)
        # Hyper-V doesn't have explicit storage pools — this is a no-op placeholder
        return True

    async def list_storage_pools(self) -> List[str]:
        script = """
        $host_info = Get-VMHost
        @($host_info.VirtualHardDiskPath, $host_info.VirtualMachinePath) | ConvertTo-Json -Compress
        """
        stdout = await self._run_powershell(script)
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return [p for p in data if p]
            return [data] if data else []
        except Exception:
            return []

    async def list_snapshots(self, vm_name: str) -> List[str]:
        validate_vm_name(vm_name)
        script = f"""
        Get-VMSnapshot -VMName '{vm_name}' | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress
        """
        stdout = await self._run_powershell(script)
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return data
            return [data] if data else []
        except Exception:
            return []

    async def export_vm(self, vm_name: str, export_path: str) -> bool:
        validate_vm_name(vm_name)
        validate_path(export_path)
        esc_path = export_path.replace("'", "''")
        script = f"""
        $ErrorActionPreference = 'Stop'
        if (-not (Test-Path '{esc_path}')) {{
            New-Item -ItemType Directory -Path '{esc_path}' -Force | Out-Null
        }}
        Export-VM -Name '{vm_name}' -Path '{esc_path}'
        """
        await self._run_powershell(script)
        return True

        script = f"""
        $ErrorActionPreference = 'Stop'
        $nic = Add-VMNetworkAdapter -VMName '{vm_name}' -SwitchName '{switch_name}' -Passthru
        $nic.MacAddress
        """
        return await self._run_powershell(script)

    # detaches interface based on unique MAC.
    async def remove_network_adapter(self, vm_name: str, adapter_mac: str) -> bool:
        validate_vm_name(vm_name)
        if not re.match(r"^[0-9a-fA-F:-]+$", adapter_mac):
            raise ValueError(f"invalid MAC address format: '{adapter_mac}'")
            
        script = f"""
        $ErrorActionPreference = 'Stop'
        $nic = Get-VMNetworkAdapter -VMName '{vm_name}' | Where-Object {{ $_.MacAddress -eq '{adapter_mac}' }}
        if (-not $nic) {{
            throw "network adapter with MAC '{adapter_mac}' not found."
        }}
        Remove-VMNetworkAdapter -VMNetworkAdapter $nic
        """
        await self._run_powershell(script)
        return True

    # --- Advanced Configuration ---
    async def enable_secure_boot(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        state = "On" if enabled else "Off"
        script = f"Set-VMFirmware -VMName '{vm_name}' -EnableSecureBoot {state}"
        await self._run_powershell(script)
        return True

    async def enable_nested_virtualization(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        state = "$true" if enabled else "$false"
        script = f"Set-VMProcessor -VMName '{vm_name}' -ExposeVirtualizationExtensions {state}"
        await self._run_powershell(script)
        return True

    async def enable_tpm(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        if enabled:
            # Enable Key Protector and vTPM
            script = f"""
            $ErrorActionPreference = 'Stop'
            $vm = Get-VM -Name '{vm_name}'
            $owner = Get-HgsGuardian UntrustedGuardian
            $kp = New-HgsKeyProtector -Owner $owner -AllowUntrustedRoot
            Set-VMKeyProtector -VMName '{vm_name}' -KeyProtector $kp.RawData
            Enable-VMTPM -VMName '{vm_name}'
            """
        else:
            script = f"Disable-VMTPM -VMName '{vm_name}'"
        await self._run_powershell(script)
        return True

    # --- Virtual Network Management ---
    async def create_network(self, name: str, subnet_cidr: str) -> bool:
        validate_vm_name(name)
        # In Hyper-V, we create an internal switch.
        # NAT routing requires New-NetNat, which is more complex, but we'll create the internal switch.
        script = f"""
        $ErrorActionPreference = 'Stop'
        $switch = Get-VMSwitch -Name '{name}' -ErrorAction SilentlyContinue
        if (-not $switch) {{
            New-VMSwitch -Name '{name}' -SwitchType Internal
        }}
        """
        await self._run_powershell(script)
        return True

    async def delete_network(self, name: str) -> bool:
        validate_vm_name(name)
        script = f"Remove-VMSwitch -Name '{name}' -Force"
        await self._run_powershell(script)
        return True

    async def list_networks(self) -> List[str]:
        script = """
        $switches = @(Get-VMSwitch)
        if ($switches) {
            $switches | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress
        } else {
            "[]"
        }
        """
        stdout = await self._run_powershell(script)
        if not stdout or stdout.strip() == "[]":
            return []
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return data
            return [data]
        except Exception:
            return []

    # --- Telemetry & Metrics ---
    async def get_vm_metrics(self, vm_name: str) -> "VMMetrics":
        from virtual_py.core.models import VMMetrics
        validate_vm_name(vm_name)
        script = f"""
        $ErrorActionPreference = 'Stop'
        $vm = Get-VM -Name '{vm_name}'
        $vm | Select-Object CPUUsage, @{{Name='MemoryDemand';Expression={{[int]($_.MemoryDemand / 1MB)}}}}, Uptime | ConvertTo-Json -Compress
        """
        try:
            stdout = await self._run_powershell(script)
            data = json.loads(stdout)
            
            uptime_str = data.get("Uptime", {}).get("TotalSeconds", 0)
            if isinstance(data.get("Uptime"), str):
                # TimeSpan string parsing if PS outputs string
                uptime_str = 0 # simplified
            elif isinstance(data.get("Uptime"), dict):
                uptime_str = data["Uptime"].get("TotalSeconds", 0)
                
            return VMMetrics(
                cpu_usage_percent=float(data.get("CPUUsage", 0)),
                memory_demand_mb=int(data.get("MemoryDemand", 0)),
                uptime_seconds=int(uptime_str)
            )
        except Exception as e:
            return VMMetrics(0.0, 0, 0)

    async def migrate_vm(self, vm_name: str, target_host: str, **kwargs) -> bool:
        validate_vm_name(vm_name)
        if not re.match(r"^[a-zA-Z0-9.-]+$", target_host):
            raise ValueError(f"invalid target host address: '{target_host}'")
        
        script = f"Move-VM -Name '{vm_name}' -DestinationHost '{target_host}' -ErrorAction Stop"
        await self._run_powershell(script)
        return True

    async def create_storage_pool(self, name: str, path: str) -> bool:
        validate_vm_name(name)
        validate_path(path)
        esc_path = path.replace("'", "''")
        script = f"""
        $ErrorActionPreference = 'Stop'
        if (-not (Test-Path '{esc_path}')) {{
            New-Item -ItemType Directory -Path '{esc_path}' -Force | Out-Null
        }}
        Set-VMHost -VirtualHardDiskPath '{esc_path}' -ErrorAction SilentlyContinue
        """
        await self._run_powershell(script)
        return True

    async def delete_storage_pool(self, name: str) -> bool:
        validate_vm_name(name)
        # Hyper-V doesn't have explicit storage pools — this is a no-op placeholder
        return True

    async def list_storage_pools(self) -> List[str]:
        script = """
        $host_info = Get-VMHost
        @($host_info.VirtualHardDiskPath, $host_info.VirtualMachinePath) | ConvertTo-Json -Compress
        """
        stdout = await self._run_powershell(script)
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return [p for p in data if p]
            return [data] if data else []
        except Exception:
            return []

    async def list_snapshots(self, vm_name: str) -> List[str]:
        validate_vm_name(vm_name)
        script = f"""
        Get-VMSnapshot -VMName '{vm_name}' | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress
        """
        stdout = await self._run_powershell(script)
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                return data
            return [data] if data else []
        except Exception:
            return []

    async def export_vm(self, vm_name: str, export_path: str) -> bool:
        validate_vm_name(vm_name)
        validate_path(export_path)
        esc_path = export_path.replace("'", "''")
        script = f"""
        $ErrorActionPreference = 'Stop'
        if (-not (Test-Path '{esc_path}')) {{
            New-Item -ItemType Directory -Path '{esc_path}' -Force | Out-Null
        }}
        Export-VM -Name '{vm_name}' -Path '{esc_path}'
        """
        await self._run_powershell(script)
        return True

    async def clone_vm(self, vm_name: str, clone_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_vm_name(clone_name)
        # Hyper-V doesn't have a native clone; export then import as a copy
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            esc_tmp = tmpdir.replace("'", "''")
            script = f"""
            $ErrorActionPreference = 'Stop'
            Export-VM -Name '{vm_name}' -Path '{esc_tmp}'
            $exported = Get-ChildItem -Path '{esc_tmp}\\{vm_name}\\Virtual Machines' -Filter '*.vmcx' | Select-Object -First 1
            $imported = Import-VM -Path $exported.FullName -Copy -GenerateNewId
            Rename-VM -VM $imported -NewName '{clone_name}'
            """
            await self._run_powershell(script)
        return True

    async def get_console_display(self, vm_name: str) -> str:
        validate_vm_name(vm_name)
        return "localhost:5900"

    async def attach_gpu(self, vm_name: str, mode: str = "shared", **kwargs) -> bool:
        validate_vm_name(vm_name)
        if mode == "shared":
            script = f"""
            $ErrorActionPreference = 'Stop'
            Add-VMGpuPartitionAdapter -VMName '{vm_name}' -ErrorAction SilentlyContinue
            Set-VMGpuPartitionAdapter -VMName '{vm_name}' -MinPartitionVRAM 80000000 -MaxPartitionVRAM 100000000 -OptimalPartitionVRAM 100000000 -MinPartitionEncode 80000000 -MaxPartitionEncode 100000000 -OptimalPartitionEncode 100000000 -MinPartitionDecode 80000000 -MaxPartitionDecode 100000000 -OptimalPartitionDecode 100000000 -MinPartitionCompute 80000000 -MaxPartitionCompute 100000000 -OptimalPartitionCompute 100000000
            """
        else:
            pci_addr = kwargs.get("pci_address")
            if not pci_addr:
                gpus = await self.detect_host_gpus()
                if gpus:
                    pci_addr = gpus[0].get("pci_address")
            if not pci_addr:
                pci_addr = "PCIROOT(0)#PCI(0200)" # fallback location path
                
            script = f"""
            $ErrorActionPreference = 'Stop'
            Dismount-VMHostAssignableDevice -LocationPath '{pci_addr}' -Force -ErrorAction SilentlyContinue
            Add-VMPciDeviceAdapter -VMName '{vm_name}' -LocationPath '{pci_addr}'
            """
        await self._run_powershell(script)
        return True
