from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class VMCreatePayload(BaseModel):
    name: str
    cpu_count: int
    memory_mb: int
    disk_path: str
    network_name: Optional[str] = None
    iso_path: Optional[str] = None
    cloud_init: Optional[Dict[str, Any]] = None
    raw_user_data: Optional[str] = None
    sysprep: Optional[Dict[str, Any]] = None

class VMScalePayload(BaseModel):
    memory_mb: Optional[int] = None
    cpu_count: Optional[int] = None
    live: bool = False

class VMConfigPayload(BaseModel):
    secure_boot: Optional[bool] = None
    nested_virt: Optional[bool] = None
    tpm: Optional[bool] = None

class NetworkCreatePayload(BaseModel):
    cidr: str

class VMInfoResponse(BaseModel):
    name: str
    status: str
    cpu_count: int
    memory_mb: int
    ip_address: Optional[str] = None

class VMMetricsResponse(BaseModel):
    cpu_usage_percent: float
    memory_demand_mb: int
    uptime_seconds: int

class HostMetricsResponse(BaseModel):
    cpu_percent: float
    memory_used_mb: int
    memory_total_mb: int

class CheckpointPayload(BaseModel):
    name: str

class VMMigratePayload(BaseModel):
    target_host: str
