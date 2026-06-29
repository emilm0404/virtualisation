import asyncio
import json
import re
import os
import base64
import random
import shutil
from typing import List, Optional
import xml.etree.ElementTree as ET
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

class KVMProvider(VMProvider):

    def __init__(self, virsh_path: str = "virsh", virt_install_path: str = "virt-install"):
        self.virsh_path = virsh_path
        self.virt_install_path = virt_install_path

    async def _run_command(self, cmd: List[str]) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
        except Exception as e:
            raise HypervisorExecutionError(
                command=" ".join(cmd),
                returncode=-1,
                stdout="",
                stderr=str(e),
                message=f"failed to run command {' '.join(cmd)} because: {str(e)}"
            )

        if proc.returncode != 0:
            raise HypervisorExecutionError(
                command=" ".join(cmd),
                returncode=proc.returncode,
                stdout=stdout.decode().strip(),
                stderr=stderr.decode().strip()
            )
        return stdout.decode().strip()

    def _parse_list(self, stdout: str) -> List[dict]:
        lines = stdout.splitlines()
        vms = []
        if len(lines) < 3:
            return vms
        
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                state_str = " ".join(parts[2:]).lower()
                status = VMStatus.UNKNOWN
                if "running" in state_str:
                    status = VMStatus.RUNNING
                elif "shut off" in state_str:
                    status = VMStatus.STOPPED
                elif "paused" in state_str:
                    status = VMStatus.PAUSED
                
                vms.append({"name": name, "status": status})
        return vms

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

        net = network_name or "default"
        
        # default size is 20G. assuming qcow2 image.
        cmd = [
            self.virt_install_path,
            "--name", name,
            "--vcpus", str(cpu_count),
            "--memory", str(memory_mb),
            "--disk", f"path={disk_path},size=20,format=qcow2",
            "--network", f"network={net}",
            "--noautoconsole",
            "--graphics", "none"
        ]
        
        # build and mount seed ISO for automatic cloud-init setup.
        if cloud_init or raw_user_data:
            from virtual_py.utils.cloudinit import create_cidata_iso
            cidata_path = os.path.join(os.path.dirname(os.path.abspath(disk_path)), f"{name}-cidata.iso")
            
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
            cmd.extend(["--disk", f"path={cidata_path},device=cdrom"])

        if sysprep:
            from virtual_py.utils.sysprep import create_unattend_iso
            unattend_path = os.path.join(os.path.dirname(os.path.abspath(disk_path)), f"{name}-unattend.iso")
            create_unattend_iso(
                output_path=unattend_path,
                hostname=sysprep.get("hostname", name),
                admin_password=sysprep.get("admin_password", "Password123!"),
                raw_unattend_xml=sysprep.get("raw_xml")
            )
            cmd.extend(["--disk", f"path={unattend_path},device=cdrom"])

        if iso_path:
            cmd.extend(["--cdrom", iso_path])
        else:
            cmd.append("--import")
        
        await self._run_command(cmd)
        return True

    async def start_vm(self, name: str) -> bool:
        validate_vm_name(name)
        try:
            await self._run_command([self.virsh_path, "start", name])
            return True
        except HypervisorExecutionError as e:
            if "domain is already active" in e.stderr.lower():
                return True
            if "failed to find" in e.stderr.lower() or "no domain with matching" in e.stderr.lower():
                raise VMNotFoundError(name)
            raise

    async def stop_vm(self, name: str, force: bool = False) -> bool:
        validate_vm_name(name)
        action = "destroy" if force else "shutdown"
        try:
            await self._run_command([self.virsh_path, action, name])
            return True
        except HypervisorExecutionError as e:
            if "domain is not running" in e.stderr.lower():
                return True
            if "failed to find" in e.stderr.lower() or "no domain with matching" in e.stderr.lower():
                raise VMNotFoundError(name)
            raise

    async def delete_vm(self, name: str) -> bool:
        validate_vm_name(name)
        try:
            await self._run_command([self.virsh_path, "undefine", name, "--remove-all-storage"])
            return True
        except HypervisorExecutionError as e:
            if "failed to find" in e.stderr.lower() or "no domain with matching" in e.stderr.lower():
                raise VMNotFoundError(name)
            raise

    async def get_vm_info(self, name: str) -> VMInfo:
        validate_vm_name(name)
        try:
            stdout = await self._run_command([self.virsh_path, "dominfo", name])
        except HypervisorExecutionError as e:
            if "failed to find" in e.stderr.lower() or "no domain with matching" in e.stderr.lower():
                raise VMNotFoundError(name)
            raise

        cpu_count = 1
        memory_mb = 1024
        status = VMStatus.UNKNOWN

        for line in stdout.splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip().lower()

            if "cpu(s)" in key:
                cpu_count = int(val)
            elif "max memory" in key:
                match = re.search(r"(\d+)\s*kiB", line, re.IGNORECASE)
                if match:
                    memory_mb = int(int(match.group(1)) / 1024)
            elif "state" in key:
                if "running" in val:
                    status = VMStatus.RUNNING
                elif "shut off" in val:
                    status = VMStatus.STOPPED
                elif "paused" in val:
                    status = VMStatus.PAUSED

        ip_addr = None
        if status == VMStatus.RUNNING:
            try:
                ip_stdout = await self._run_command([self.virsh_path, "domifaddr", name])
                for line in ip_stdout.splitlines():
                    if "ipv4" in line or "/" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            ip_addr = parts[3].split("/")[0]
                            break
            except Exception:
                # guest might not have lease or agent isn't reporting yet.
                pass

        return VMInfo(
            name=name,
            status=status,
            memory_mb=memory_mb,
            cpu_count=cpu_count,
            ip_address=ip_addr
        )

    async def list_vms(self) -> List[VMInfo]:
        stdout = await self._run_command([self.virsh_path, "list", "--all"])
        parsed = self._parse_list(stdout)
        vms = []
        for item in parsed:
            try:
                info = await self.get_vm_info(item["name"])
                vms.append(info)
            except VMNotFoundError:
                # transient check. could have been deleted during list traversal.
                continue
        return vms

    async def create_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_checkpoint_name(checkpoint_name)
        await self._run_command([self.virsh_path, "snapshot-create-as", vm_name, checkpoint_name])
        return True

    async def restore_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_checkpoint_name(checkpoint_name)
        await self._run_command([self.virsh_path, "snapshot-revert", vm_name, checkpoint_name])
        return True

    async def delete_checkpoint(self, vm_name: str, checkpoint_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_checkpoint_name(checkpoint_name)
        await self._run_command([self.virsh_path, "snapshot-delete", vm_name, checkpoint_name])
        return True

    async def list_checkpoints(self, vm_name: str) -> List[str]:
        validate_vm_name(vm_name)
        stdout = await self._run_command([self.virsh_path, "snapshot-list", vm_name, "--name"])
        return [line.strip() for line in stdout.splitlines() if line.strip()]

    async def execute_command(
        self,
        vm_name: str,
        command: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> str:
        validate_vm_name(vm_name)
        # run /bin/sh to support pipes and multiple script commands.
        payload = {
            "execute": "guest-exec",
            "arguments": {
                "path": "/bin/sh",
                "arg": ["-c", command],
                "capture-output": True
            }
        }
        
        raw_res = await self._run_command([
            self.virsh_path,
            "qemu-agent-command",
            vm_name,
            json.dumps(payload)
        ])
        
        res = json.loads(raw_res)
        pid = res.get("return", {}).get("pid")
        if not pid:
            raise HypervisorExecutionError(command, -1, "", "", "failed to acquire guest agent execution pid.")

        # poll agent until exit status is returned.
        status_payload = {
            "execute": "guest-exec-status",
            "arguments": {"pid": pid}
        }
        
        for _ in range(30):
            status_res = await self._run_command([
                self.virsh_path,
                "qemu-agent-command",
                vm_name,
                json.dumps(status_payload)
            ])
            status_data = json.loads(status_res).get("return", {})
            if status_data.get("exited", False):
                exitcode = status_data.get("exitcode", 0)
                out_b64 = status_data.get("out-data", "")
                err_b64 = status_data.get("err-data", "")
                
                out = base64.b64decode(out_b64).decode(errors="replace") if out_b64 else ""
                err = base64.b64decode(err_b64).decode(errors="replace") if err_b64 else ""
                
                if exitcode != 0:
                    raise HypervisorExecutionError(command, exitcode, out, err)
                return out
            await asyncio.sleep(1)
            
        raise TimeoutError(f"timed out waiting for guest command execution pid {pid}.")

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
        
        if not os.path.exists(host_path):
            raise FileNotFoundError(f"host file not found: {host_path}")
            
        with open(host_path, "rb") as f:
            content = f.read()
            
        encoded = base64.b64encode(content).decode()
        
        # open file handle.
        open_payload = {
            "execute": "guest-file-open",
            "arguments": {"path": guest_path, "mode": "wb"}
        }
        open_res = await self._run_command([
            self.virsh_path,
            "qemu-agent-command",
            vm_name,
            json.dumps(open_payload)
        ])
        handle = json.loads(open_res).get("return")
        
        try:
            # write buffer content.
            write_payload = {
                "execute": "guest-file-write",
                "arguments": {"handle": handle, "buf-b64": encoded}
            }
            await self._run_command([
                self.virsh_path,
                "qemu-agent-command",
                vm_name,
                json.dumps(write_payload)
            ])
        finally:
            # close file handle.
            close_payload = {
                "execute": "guest-file-close",
                "arguments": {"handle": handle}
            }
            await self._run_command([
                self.virsh_path,
                "qemu-agent-command",
                vm_name,
                json.dumps(close_payload)
            ])
            
        return True

    async def set_vm_memory(self, vm_name: str, memory_mb: int, live: bool = False) -> bool:
        validate_vm_name(vm_name)
        # persistent configuration
        await self._run_command([self.virsh_path, "setmaxmem", vm_name, f"{memory_mb}M", "--config"])
        await self._run_command([self.virsh_path, "setmem", vm_name, f"{memory_mb}M", "--config"])
        
        if live:
            try:
                await self._run_command([self.virsh_path, "setmem", vm_name, f"{memory_mb}M", "--live"])
            except Exception:
                # guest kernel might reject live sizing or balloon driver not active.
                pass
        return True

    async def set_vm_cpus(self, vm_name: str, cpu_count: int, live: bool = False) -> bool:
        validate_vm_name(vm_name)
        await self._run_command([self.virsh_path, "setvcpus", vm_name, str(cpu_count), "--config", "--maximum"])
        await self._run_command([self.virsh_path, "setvcpus", vm_name, str(cpu_count), "--config"])
        
        if live:
            try:
                await self._run_command([self.virsh_path, "setvcpus", vm_name, str(cpu_count), "--live"])
            except Exception:
                # some guest operating systems do not support core hot-plug.
                pass
        return True

    async def _find_free_disk_target(self, vm_name: str) -> str:
        stdout = await self._run_command([self.virsh_path, "domblklist", vm_name])
        used = set(re.findall(r'vd[a-z]', stdout))
        for char in "abcdefghijklmnopqrstuvwxyz":
            candidate = f"vd{char}"
            if candidate not in used:
                return candidate
        return "vdz"

    async def attach_disk(self, vm_name: str, disk_path: str, controller_type: Optional[str] = None) -> bool:
        validate_vm_name(vm_name)
        validate_path(disk_path)
        
        target = await self._find_free_disk_target(vm_name)
        info = await self.get_vm_info(vm_name)
        
        cmd = [self.virsh_path, "attach-disk", vm_name, disk_path, target, "--subdriver", "qcow2", "--config"]
        if info.status == VMStatus.RUNNING:
            cmd.append("--live")
            
        await self._run_command(cmd)
        return True

    async def detach_disk(self, vm_name: str, disk_path: str) -> bool:
        validate_vm_name(vm_name)
        validate_path(disk_path)
        
        stdout = await self._run_command([self.virsh_path, "domblklist", vm_name])
        target = None
        for line in stdout.splitlines():
            if disk_path in line or os.path.basename(disk_path) in line:
                parts = line.split()
                if len(parts) >= 2:
                    target = parts[0]
                    break
                    
        if not target:
            raise ValueError(f"virtual disk path '{disk_path}' is not attached to vm '{vm_name}'.")
            
        info = await self.get_vm_info(vm_name)
        cmd = [self.virsh_path, "detach-disk", vm_name, target, "--config"]
        if info.status == VMStatus.RUNNING:
            cmd.append("--live")
            
        await self._run_command(cmd)
        return True

    async def add_network_adapter(self, vm_name: str, switch_name: str) -> str:
        validate_vm_name(vm_name)
        validate_vm_name(switch_name)
        
        mac = "52:54:00:%02x:%02x:%02x" % (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        info = await self.get_vm_info(vm_name)
        
        cmd = [
            self.virsh_path,
            "attach-interface",
            vm_name,
            "--type", "network",
            "--source", switch_name,
            "--model", "virtio",
            "--mac", mac,
            "--config"
        ]
        if info.status == VMStatus.RUNNING:
            cmd.append("--live")
            
        await self._run_command(cmd)
        return mac

    async def remove_network_adapter(self, vm_name: str, adapter_mac: str) -> bool:
        validate_vm_name(vm_name)
        # MAC sanitization checks format
        if not re.match(r"^[0-9a-fA-F:-]+$", adapter_mac):
            raise ValueError(f"invalid MAC address format: '{adapter_mac}'")
            
        info = await self.get_vm_info(vm_name)
        cmd = [
            self.virsh_path,
            "detach-interface",
            vm_name,
            "--type", "network",
            "--mac", adapter_mac,
            "--config"
        ]
        if info.status == VMStatus.RUNNING:
            cmd.append("--live")
            
        await self._run_command(cmd)
        return True

    # --- Advanced Configuration ---
    async def enable_secure_boot(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        # using virt-xml if available is best, but we'll try to execute it as a virsh wrapper.
        # for true robustness without virt-xml, we dump, patch, and define.
        xml = await self._run_command([self.virsh_path, "dumpxml", vm_name])
        
        if enabled:
            if "<loader secure='yes'" not in xml:
                # Basic injection (highly simplified for demonstration, typically requires OVMF path)
                xml = xml.replace("<os>", "<os>\n    <loader readonly='yes' type='pflash' secure='yes'>/usr/share/OVMF/OVMF_CODE.secboot.fd</loader>")
        else:
            xml = re.sub(r"<loader.*?secure='yes'.*?</loader>", "", xml)
            
        # Write back to a temp file and define
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(xml)
            temp_name = f.name
            
        try:
            await self._run_command([self.virsh_path, "define", temp_name])
        finally:
            os.remove(temp_name)
        return True

    async def enable_nested_virtualization(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        xml = await self._run_command([self.virsh_path, "dumpxml", vm_name])
        
        if enabled:
            if "host-passthrough" not in xml:
                xml = re.sub(r"<cpu.*?>", "<cpu mode='host-passthrough'>", xml)
        else:
            xml = re.sub(r"<cpu mode='host-passthrough'>", "<cpu mode='custom'>", xml)
            
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(xml)
            temp_name = f.name
            
        try:
            await self._run_command([self.virsh_path, "define", temp_name])
        finally:
            os.remove(temp_name)
        return True

    async def enable_tpm(self, vm_name: str, enabled: bool) -> bool:
        validate_vm_name(vm_name)
        xml = await self._run_command([self.virsh_path, "dumpxml", vm_name])
        
        if enabled:
            if "<tpm" not in xml:
                tpm_xml = "<tpm model='tpm-crb'><backend type='emulator' version='2.0'/></tpm>"
                xml = xml.replace("</devices>", f"  {tpm_xml}\n  </devices>")
        else:
            xml = re.sub(r"<tpm.*?</tpm>", "", xml, flags=re.DOTALL)
            
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(xml)
            temp_name = f.name
            
        try:
            await self._run_command([self.virsh_path, "define", temp_name])
        finally:
            os.remove(temp_name)
        return True

    # --- Virtual Network Management ---
    async def create_network(self, name: str, subnet_cidr: str) -> bool:
        validate_vm_name(name)
        # subnet_cidr e.g., "192.168.100.0/24" -> parse to gateway 192.168.100.1
        parts = subnet_cidr.split(".")
        if len(parts) == 4:
            gw = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
            start_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.10"
            end_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.254"
        else:
            gw = "192.168.100.1"
            start_ip = "192.168.100.10"
            end_ip = "192.168.100.254"

        net_xml = f"""
        <network>
          <name>{name}</name>
          <forward mode='nat'/>
          <bridge name='virbr_{name[:8]}' stp='on' delay='0'/>
          <ip address='{gw}' netmask='255.255.255.0'>
            <dhcp>
              <range start='{start_ip}' end='{end_ip}'/>
            </dhcp>
          </ip>
        </network>
        """
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(net_xml)
            temp_name = f.name
            
        try:
            await self._run_command([self.virsh_path, "net-define", temp_name])
            await self._run_command([self.virsh_path, "net-start", name])
            await self._run_command([self.virsh_path, "net-autostart", name])
        finally:
            os.remove(temp_name)
        return True

    async def delete_network(self, name: str) -> bool:
        validate_vm_name(name)
        try:
            await self._run_command([self.virsh_path, "net-destroy", name])
        except HypervisorExecutionError:
            pass # ignore if already stopped
        await self._run_command([self.virsh_path, "net-undefine", name])
        return True

    async def list_networks(self) -> List[str]:
        stdout = await self._run_command([self.virsh_path, "net-list", "--all"])
        networks = []
        for line in stdout.splitlines()[2:]:
            parts = line.split()
            if len(parts) >= 1:
                networks.append(parts[0])
        return networks

    # --- Telemetry & Metrics ---
    async def get_vm_metrics(self, vm_name: str) -> "VMMetrics":
        from virtual_py.core.models import VMMetrics
        validate_vm_name(vm_name)
        try:
            stdout = await self._run_command([self.virsh_path, "domstats", vm_name])
            
            cpu_usage = 0.0
            mem_demand = 0
            
            # Simple parse of domstats
            for line in stdout.splitlines():
                if "cpu.time=" in line:
                    cpu_time = float(line.split("=")[1])
                    cpu_usage = min(100.0, cpu_time / 1e9) # Very rough approximation for display
                elif "balloon.current=" in line:
                    mem_demand = int(line.split("=")[1]) // 1024
                    
            return VMMetrics(
                cpu_usage_percent=round(cpu_usage, 2),
                memory_demand_mb=mem_demand,
                uptime_seconds=0 # requires more complex parsing in KVM
            )
        except Exception:
            return VMMetrics(0.0, 0, 0)

    async def migrate_vm(self, vm_name: str, target_host: str, **kwargs) -> bool:
        validate_vm_name(vm_name)
        if not re.match(r"^[a-zA-Z0-9.-]+$", target_host):
            raise ValueError(f"invalid target host address: '{target_host}'")
        
        dest_uri = f"qemu+ssh://{target_host}/system"
        cmd = [self.virsh_path, "migrate", "--live", vm_name, dest_uri]
        await self._run_command(cmd)
        return True

    async def create_storage_pool(self, name: str, path: str) -> bool:
        validate_vm_name(name)
        validate_path(path)
        await self._run_command([self.virsh_path, "pool-define-as", name, "dir", "--target", path])
        try:
            await self._run_command([self.virsh_path, "pool-build", name])
        except HypervisorExecutionError:
            pass
        await self._run_command([self.virsh_path, "pool-start", name])
        await self._run_command([self.virsh_path, "pool-autostart", name])
        return True

    async def delete_storage_pool(self, name: str) -> bool:
        validate_vm_name(name)
        try:
            await self._run_command([self.virsh_path, "pool-destroy", name])
        except HypervisorExecutionError:
            pass
        await self._run_command([self.virsh_path, "pool-undefine", name])
        return True

    async def list_storage_pools(self) -> List[str]:
        stdout = await self._run_command([self.virsh_path, "pool-list", "--all", "--name"])
        return [line.strip() for line in stdout.splitlines() if line.strip()]

    async def list_snapshots(self, vm_name: str) -> List[str]:
        validate_vm_name(vm_name)
        stdout = await self._run_command([self.virsh_path, "snapshot-list", vm_name, "--name"])
        return [line.strip() for line in stdout.splitlines() if line.strip()]

    async def export_vm(self, vm_name: str, export_path: str) -> bool:
        validate_vm_name(vm_name)
        validate_path(export_path)
        # Dump the VM's XML definition to the export path
        stdout = await self._run_command([self.virsh_path, "dumpxml", vm_name])
        xml_path = os.path.join(export_path, f"{vm_name}.xml")
        os.makedirs(export_path, exist_ok=True)
        with open(xml_path, "w") as f:
            f.write(stdout)
        return True

    async def clone_vm(self, vm_name: str, clone_name: str) -> bool:
        validate_vm_name(vm_name)
        validate_vm_name(clone_name)
        virt_clone = shutil.which("virt-clone")
        if not virt_clone:
            raise HypervisorExecutionError("virt-clone not found on PATH")
        await self._run_command([
            virt_clone,
            "--original", vm_name,
            "--name", clone_name,
            "--auto-clone"
        ])
        return True

    async def get_console_display(self, vm_name: str) -> str:
        validate_vm_name(vm_name)
        try:
            stdout = await self._run_command([self.virsh_path, "domdisplay", vm_name])
            return stdout.strip()
        except Exception:
            return "localhost:5900"

    async def attach_gpu(self, vm_name: str, mode: str = "shared", **kwargs) -> bool:
        validate_vm_name(vm_name)
        stdout = await self._run_command([self.virsh_path, "dumpxml", vm_name])
        
        root = ET.fromstring(stdout)
        devices = root.find("devices")
        if devices is None:
            raise HypervisorExecutionError(command="dumpxml", returncode=-1, stdout="", stderr="no devices block in xml")
            
        if mode == "shared":
            # remove old video tags.
            for video in list(devices.findall("video")):
                devices.remove(video)
            
            # create accelerated virtio element.
            video = ET.SubElement(devices, "video")
            model = ET.SubElement(video, "model", type="virtio", heads="1", primary="yes")
            ET.SubElement(model, "acceleration", accel3d="yes")
        else:
            # full pci passthrough.
            pci_addr = kwargs.get("pci_address")
            if not pci_addr:
                gpus = await self.detect_host_gpus()
                if gpus:
                    pci_addr = gpus[0].get("pci_address")
            if not pci_addr:
                pci_addr = "0000:01:00.0"
                
            # parse e.g. 0000:01:00.0.
            parts = pci_addr.replace(".", ":").split(":")
            if len(parts) >= 4:
                domain_val = f"0x{parts[0]}"
                bus_val = f"0x{parts[1]}"
                slot_val = f"0x{parts[2]}"
                func_val = f"0x{parts[3]}"
            else:
                domain_val, bus_val, slot_val, func_val = "0x0000", "0x01", "0x00", "0x0"
                
            # create hostdev entry.
            hostdev = ET.SubElement(devices, "hostdev", mode="subsystem", type="pci", managed="yes")
            source = ET.SubElement(hostdev, "source")
            ET.SubElement(source, "address", domain=domain_val, bus=bus_val, slot=slot_val, function=func_val)
            
        import xml.etree.ElementTree as ET
        import tempfile
        xml_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        fd, path = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml_str)
            await self._run_command([self.virsh_path, "define", path])
        finally:
            if os.path.exists(path):
                os.remove(path)
        return True
