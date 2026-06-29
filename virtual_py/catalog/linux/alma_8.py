from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="alma-8",
    name="AlmaLinux 8.9",
    arch="x86_64",
    url="https://repo.almalinux.org/almalinux/8.9/isos/x86_64/AlmaLinux-8.9-x86_64-minimal.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
