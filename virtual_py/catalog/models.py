from dataclasses import dataclass
from typing import Optional

@dataclass
class OSTemplate:
    id: str
    name: str
    arch: str
    url: str
    min_memory_mb: int
    min_cpu_count: int
    cloud_init_supported: bool
    default_username: str
    # optional checksum for validation
    sha256_checksum: Optional[str] = None
    # indicates if the upstream URL is still valid and reachable
    available: bool = True
