from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="archlinux",
    name="Arch Linux",
    arch="x86_64",
    url="https://geo.mirror.pkgbuild.com/iso/latest/archlinux-x86_64.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
