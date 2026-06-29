from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="centos-7",
    name="CentOS 7 (Core)",
    arch="x86_64",
    url="https://mirrors.edge.kernel.org/centos/7/isos/x86_64/CentOS-7-x86_64-Minimal-2009.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
