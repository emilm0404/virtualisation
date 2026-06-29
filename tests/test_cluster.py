import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from virtual_py.api.cluster import ClusterManager

@pytest.mark.asyncio
async def test_get_least_loaded_node():
    manager = ClusterManager(["http://node1", "http://node2", "http://node3"])

    async def mock_get(url, timeout):
        response = MagicMock()
        if "node1" in url:
            # Load = 50% CPU + 50% Mem = 100
            response.status_code = 200
            response.json.return_value = {"cpu_percent": 50.0, "memory_used_mb": 1024, "memory_total_mb": 2048}
            return response
        elif "node2" in url:
            # Load = 10% CPU + 20% Mem = 30 (Best)
            response.status_code = 200
            response.json.return_value = {"cpu_percent": 10.0, "memory_used_mb": 204, "memory_total_mb": 1024}
            return response
        else:
            # Node 3 is down
            raise Exception("Connection timeout")

    with patch("virtual_py.api.cluster.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(side_effect=mock_get)
        
        # httpx.AsyncClient is used as an async context manager
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        
        mock_client.return_value = mock_instance

        best = await manager.get_least_loaded_node()
        assert best == "http://node2"

@pytest.mark.asyncio
async def test_empty_cluster():
    manager = ClusterManager([])
    best = await manager.get_least_loaded_node()
    assert best is None
