from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="ubuntu-22.04",
    name="Ubuntu 22.04 LTS",
    arch="x86_64",
    url="https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
