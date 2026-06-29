import httpx
import asyncio
from typing import List, Optional

class ClusterManager:
    def __init__(self, node_urls: List[str]):
        self.node_urls = [url.rstrip('/') for url in node_urls]

    async def _get_node_load(self, url: str) -> Optional[float]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/system/metrics", timeout=2.0)
                if response.status_code == 200:
                    data = response.json()
                    # simple heuristic: sum of cpu % and memory utilization %
                    mem_pct = (data["memory_used_mb"] / data["memory_total_mb"]) * 100
                    return data["cpu_percent"] + mem_pct
        except Exception:
            pass
        return float('inf') # node is down or unreachable

    async def get_least_loaded_node(self) -> Optional[str]:
        if not self.node_urls:
            return None
        
        tasks = [self._get_node_load(url) for url in self.node_urls]
        loads = await asyncio.gather(*tasks)
        
        best_node = None
        best_load = float('inf')
        
        for url, load in zip(self.node_urls, loads):
            if load < best_load:
                best_load = load
                best_node = url
                
        return best_node
