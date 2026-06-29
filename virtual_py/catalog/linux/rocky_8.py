from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="rocky-8",
    name="Rocky Linux 8.9",
    arch="x86_64",
    url="https://download.rockylinux.org/pub/rocky/8/isos/x86_64/Rocky-8-latest-x86_64-minimal.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
