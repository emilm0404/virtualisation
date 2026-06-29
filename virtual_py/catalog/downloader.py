import os
import urllib.request
import asyncio
from typing import Callable, Optional

async def download_iso_async(
    url: str, 
    dest_path: str, 
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Downloads an ISO file asynchronously using a thread executor to avoid blocking the event loop.
    Provides optional progress tracking callback.
    """
    def _download():
        if os.path.exists(dest_path):
            # rudimentary cache check. todo: add sha256 checksum validation.
            # assuming if it exists and size > 0, it is cached.
            if os.path.getsize(dest_path) > 0:
                return dest_path

        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        
        with urllib.request.urlopen(url) as response, open(dest_path, 'wb') as out_file:
            total_size = int(response.info().get('Content-Length', 0))
            chunk_size = 8192
            downloaded = 0
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)
                    
        return dest_path

    return await asyncio.to_thread(_download)
