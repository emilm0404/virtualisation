from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="ubuntu-20.04",
    name="Ubuntu 20.04 LTS",
    arch="x86_64",
    url="https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
