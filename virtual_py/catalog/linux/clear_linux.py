from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="clear-linux",
    name="Clear Linux OS",
    arch="x86_64",
    url="https://cdn.download.clearlinux.org/releases/41300/clear/clear-41300-live-server.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
