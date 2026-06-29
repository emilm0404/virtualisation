from dataclasses import dataclass
from typing import Optional

# standard state strings we use across all providers.
class VMStatus:
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    UNKNOWN = "unknown"

# generic vm info model to pass data back to business logic.
@dataclass
class VMInfo:
    name: str
    status: str
    memory_mb: int
    cpu_count: int
    ip_address: Optional[str] = None

    # easy serialize for the rest/db client.
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "memory_mb": self.memory_mb,
            "cpu_count": self.cpu_count,
            "ip_address": self.ip_address,
        }

@dataclass
class VMMetrics:
    cpu_usage_percent: float
    memory_demand_mb: int
    uptime_seconds: int
