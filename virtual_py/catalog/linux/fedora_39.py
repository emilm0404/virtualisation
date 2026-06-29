from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="fedora-39",
    name="Fedora Server 39",
    arch="x86_64",
    url="https://download.fedoraproject.org/pub/fedora/linux/releases/39/Server/x86_64/iso/Fedora-Server-netinst-x86_64-39-1.5.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
