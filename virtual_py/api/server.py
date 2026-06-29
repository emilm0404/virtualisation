from fastapi import FastAPI, HTTPException, Depends
from typing import List
from virtual_py.api.models import (
    VMCreatePayload, VMScalePayload, VMConfigPayload,
    NetworkCreatePayload, VMInfoResponse, VMMetricsResponse,
    HostMetricsResponse, CheckpointPayload, VMMigratePayload
)
from virtual_py import get_provider
from virtual_py.core.interfaces import VMProvider
from virtual_py.core.exceptions import VMException, VMNotFoundError

app = FastAPI(title="virtual-pyd", description="virtual-py Distributed Daemon REST API")

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
