from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="talos-linux",
    name="Talos Linux",
    arch="x86_64",
    url="https://github.com/siderolabs/talos/releases/download/v1.6.7/metal-amd64.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
