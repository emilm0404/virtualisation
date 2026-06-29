from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List
import base64
import os
import tempfile
from virtual_py.api.models import (
    VMCreatePayload, VMScalePayload, VMConfigPayload,
    NetworkCreatePayload, VMInfoResponse, VMMetricsResponse,
    HostMetricsResponse, CheckpointPayload, VMMigratePayload,
    GuestExecutePayload, GuestFileCopyPayload, DiskAttachPayload,
    DiskDetachPayload, AdapterAttachPayload
)
from virtual_py import get_provider
from virtual_py.core.interfaces import VMProvider
from virtual_py.core.exceptions import VMException, VMNotFoundError
from virtual_py.api.autoscaler import Autoscaler

app = FastAPI(title="virtual-pyd", description="virtual-py Distributed Daemon REST API")
autoscaler = Autoscaler(interval_seconds=10)

@app.on_event("startup")
async def startup_event():
    await autoscaler.start()

@app.on_event("shutdown")
async def shutdown_event():
    await autoscaler.stop()

# Dependency injection for the provider
def get_vm_provider() -> VMProvider:
    try:
        return get_provider()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vms", response_model=List[VMInfoResponse])
async def list_vms(provider: VMProvider = Depends(get_vm_provider)):
    vms = await provider.list_vms()
    return [{"name": vm.name, "status": vm.status, "cpu_count": vm.cpu_count, "memory_mb": vm.memory_mb, "ip_address": vm.ip_address} for vm in vms]

@app.get("/vms/{name}", response_model=VMInfoResponse)
async def get_vm_info(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        vm = await provider.get_vm_info(name)
        return {"name": vm.name, "status": vm.status, "cpu_count": vm.cpu_count, "memory_mb": vm.memory_mb, "ip_address": vm.ip_address}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms")
async def create_vm(payload: VMCreatePayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.create_vm(
            name=payload.name,
            cpu_count=payload.cpu_count,
            memory_mb=payload.memory_mb,
            disk_path=payload.disk_path,
            network_name=payload.network_name,
            iso_path=payload.iso_path,
            cloud_init=payload.cloud_init,
            raw_user_data=payload.raw_user_data,
            sysprep=payload.sysprep
        )
        return {"message": f"VM '{payload.name}' created"}
    except VMException as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/vms/{name}")
async def delete_vm(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.delete_vm(name)
        return {"message": f"VM '{name}' deleted"}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/start")
async def start_vm(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.start_vm(name)
        return {"message": f"VM '{name}' started"}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/stop")
async def stop_vm(name: str, force: bool = False, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.stop_vm(name, force=force)
        return {"message": f"VM '{name}' stopped"}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/vms/{name}/scale")
async def scale_vm(name: str, payload: VMScalePayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        if payload.memory_mb:
            await provider.set_vm_memory(name, payload.memory_mb, live=payload.live)
        if payload.cpu_count:
            await provider.set_vm_cpus(name, payload.cpu_count, live=payload.live)
        return {"message": f"VM '{name}' scaled"}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/vms/{name}/config")
async def config_vm(name: str, payload: VMConfigPayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        if payload.secure_boot is not None:
            await provider.enable_secure_boot(name, payload.secure_boot)
        if payload.nested_virt is not None:
            await provider.enable_nested_virtualization(name, payload.nested_virt)
        if payload.tpm is not None:
            await provider.enable_tpm(name, payload.tpm)
        return {"message": f"VM '{name}' configured"}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vms/{name}/metrics", response_model=VMMetricsResponse)
async def get_vm_metrics(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        metrics = await provider.get_vm_metrics(name)
        return {
            "cpu_usage_percent": metrics.cpu_usage_percent,
            "memory_demand_mb": metrics.memory_demand_mb,
            "uptime_seconds": metrics.uptime_seconds
        }
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/migrate")
async def migrate_vm(name: str, payload: VMMigratePayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.migrate_vm(name, payload.target_host)
        return {"message": f"VM '{name}' successfully migrated to '{payload.target_host}'"}
    except VMNotFoundError:
        raise HTTPException(status_code=404, detail="VM not found")
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/system/metrics", response_model=HostMetricsResponse)
async def get_system_metrics():
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_used_mb": mem.used // (1024 * 1024),
            "memory_total_mb": mem.total // (1024 * 1024)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Network routes
@app.get("/networks", response_model=List[str])
async def list_networks(provider: VMProvider = Depends(get_vm_provider)):
    return await provider.list_networks()

@app.post("/networks/{name}")
async def create_network(name: str, payload: NetworkCreatePayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.create_network(name, payload.cidr)
        return {"message": f"Network '{name}' created"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/networks/{name}")
async def delete_network(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.delete_network(name)
        return {"message": f"Network '{name}' deleted"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Storage pool routes
@app.get("/storage", response_model=List[str])
async def list_storage_pools(provider: VMProvider = Depends(get_vm_provider)):
    return await provider.list_storage_pools()

@app.post("/storage/{name}")
async def create_storage_pool(name: str, payload: dict, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.create_storage_pool(name, payload.get("path", ""))
        return {"message": f"Storage pool '{name}' created"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/storage/{name}")
async def delete_storage_pool(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.delete_storage_pool(name)
        return {"message": f"Storage pool '{name}' deleted"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Snapshot routes
@app.get("/vms/{name}/snapshots", response_model=List[str])
async def list_snapshots(name: str, provider: VMProvider = Depends(get_vm_provider)):
    return await provider.list_snapshots(name)

# Export / Clone routes
@app.post("/vms/{name}/export")
async def export_vm(name: str, payload: dict, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.export_vm(name, payload.get("export_path", ""))
        return {"message": f"VM '{name}' exported"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/vms/{name}/clone")
async def clone_vm(name: str, payload: dict, provider: VMProvider = Depends(get_vm_provider)):
    try:
        clone_name = payload.get("clone_name", "")
        await provider.clone_vm(name, clone_name)
        return {"message": f"VM '{name}' cloned as '{clone_name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# checkpoint routes.
@app.get("/vms/{name}/checkpoints", response_model=List[str])
async def list_checkpoints(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        return await provider.list_checkpoints(name)
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/checkpoints")
async def create_checkpoint(name: str, payload: CheckpointPayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.create_checkpoint(name, payload.name)
        return {"message": f"Checkpoint '{payload.name}' created for VM '{name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/checkpoints/{checkpoint_name}/restore")
async def restore_checkpoint(name: str, checkpoint_name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.restore_checkpoint(name, checkpoint_name)
        return {"message": f"VM '{name}' restored to checkpoint '{checkpoint_name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vms/{name}/checkpoints/{checkpoint_name}")
async def delete_checkpoint(name: str, checkpoint_name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.delete_checkpoint(name, checkpoint_name)
        return {"message": f"Checkpoint '{checkpoint_name}' deleted for VM '{name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

# guest execution and file operations.
@app.post("/vms/{name}/execute")
async def execute_command(name: str, payload: GuestExecutePayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        result = await provider.execute_command(
            name, payload.command,
            username=payload.username, password=payload.password
        )
        return {"output": result}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/copy-to-guest")
async def copy_to_guest(name: str, payload: GuestFileCopyPayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        if payload.file_content_b64:
            content = base64.b64decode(payload.file_content_b64)
            # save content to a temporary file on the host machine.
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                temp_path = tmp.name
            try:
                await provider.copy_file_to_guest(
                    name, temp_path, payload.guest_path,
                    username=payload.username, password=payload.password
                )
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        elif payload.host_path:
            await provider.copy_file_to_guest(
                name, payload.host_path, payload.guest_path,
                username=payload.username, password=payload.password
            )
        else:
            raise HTTPException(status_code=400, detail="Must provide either host_path or file_content_b64")
        return {"message": f"Successfully copied file to guest path '{payload.guest_path}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

# device management and hot-plugging.
@app.post("/vms/{name}/disks")
async def attach_disk(name: str, payload: DiskAttachPayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.attach_disk(name, payload.disk_path, controller_type=payload.controller_type)
        return {"message": f"Successfully attached disk '{payload.disk_path}' to VM '{name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vms/{name}/disks")
async def detach_disk(name: str, payload: DiskDetachPayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.detach_disk(name, payload.disk_path)
        return {"message": f"Successfully detached disk '{payload.disk_path}' from VM '{name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vms/{name}/network-adapters")
async def add_network_adapter(name: str, payload: AdapterAttachPayload, provider: VMProvider = Depends(get_vm_provider)):
    try:
        mac = await provider.add_network_adapter(name, payload.switch_name)
        return {"mac_address": mac}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/vms/{name}/network-adapters/{mac}")
async def remove_network_adapter(name: str, mac: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        await provider.remove_network_adapter(name, mac)
        return {"message": f"Successfully removed adapter with MAC '{mac}' from VM '{name}'"}
    except VMException as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vms/{name}/console-display")
async def get_console_display_route(name: str, provider: VMProvider = Depends(get_vm_provider)):
    try:
        return await provider.get_console_display(name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def remove_temp_file(path: str):
    if os.path.exists(path):
        os.remove(path)

@app.get("/vms/{name}/backup")
async def backup_vm_route(name: str, background_tasks: BackgroundTasks, provider: VMProvider = Depends(get_vm_provider)):
    try:
        from virtual_py.utils.backup import create_backup
        fd, path = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)
        
        await create_backup(name, path)
        background_tasks.add_task(remove_temp_file, path)
        return FileResponse(path, media_type="application/gzip", filename=f"{name}-backup.tar.gz")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/vms/{name}/console")
async def console_websocket(websocket: WebSocket, name: str, provider: VMProvider = Depends(get_vm_provider)):
    await websocket.accept()
    try:
        display_url = await provider.get_console_display(name)
        host = "127.0.0.1"
        port = 5900
        if "127.0.0.1" in display_url or "localhost" in display_url:
            if ":" in display_url:
                try:
                    port = int(display_url.split(":")[-1])
                except ValueError:
                    pass
        
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        await websocket.close(code=1011, reason=f"Failed to connect to console port: {str(e)}")
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    import asyncio
    t1 = asyncio.create_task(ws_to_tcp())
    t2 = asyncio.create_task(tcp_to_ws())
    await asyncio.gather(t1, t2, return_exceptions=True)
