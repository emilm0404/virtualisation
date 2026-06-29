from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="rocky-9",
    name="Rocky Linux 9.3",
    arch="x86_64",
    url="https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9-latest-x86_64-minimal.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
