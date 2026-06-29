from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="win11-arm",
    name="Windows 11 ARM64",
    arch="arm64",
    url="https://go.microsoft.com/fwlink/p/?LinkID=2195164",
    min_memory_mb=4096,
    min_cpu_count=2,
    cloud_init_supported=False,
    default_username="Administrator"
)

TEMPLATES = [template]
