from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="centos-9-stream",
    name="CentOS Stream 9",
    arch="x86_64",
    url="https://mirrors.edge.kernel.org/centos-stream/9-stream/BaseOS/x86_64/iso/CentOS-Stream-9-latest-x86_64-boot.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
