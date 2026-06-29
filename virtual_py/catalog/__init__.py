from .models import OSTemplate
from .registry import CatalogRegistry, default_registry
from .downloader import download_iso_async

from .linux import TEMPLATES as LINUX_TEMPLATES
from .windows import TEMPLATES as WINDOWS_TEMPLATES

for tpl in LINUX_TEMPLATES + WINDOWS_TEMPLATES:
    default_registry.register(tpl)

__all__ = [
    "OSTemplate",
    "CatalogRegistry",
    "default_registry",
    "download_iso_async"
]
