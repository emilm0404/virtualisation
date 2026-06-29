from virtual_py.catalog.models import OSTemplate

debian_12 = OSTemplate(
    id="debian-12",
    name="Debian 12 (Bookworm) Netinst",
    arch="x86_64",
    url="https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.5.0-amd64-netinst.iso",
    min_memory_mb=1024,
    min_cpu_count=1,
    cloud_init_supported=True,
    default_username="debian"
)

TEMPLATES = [debian_12]
