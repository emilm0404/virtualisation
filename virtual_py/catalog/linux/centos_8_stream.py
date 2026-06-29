from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="centos-8-stream",
    name="CentOS Stream 8",
    arch="x86_64",
    url="https://mirrors.edge.kernel.org/centos/8-stream/isos/x86_64/CentOS-Stream-8-x86_64-latest-boot.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
