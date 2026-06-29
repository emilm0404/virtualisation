from virtual_py.catalog.models import OSTemplate

alpine_3_20 = OSTemplate(
    id="alpine-3.20",
    name="Alpine Linux 3.20 (Virtual)",
    arch="x86_64",
    url="https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-virt-3.20.0-x86_64.iso",
    min_memory_mb=256,
    min_cpu_count=1,
    cloud_init_supported=True,
    default_username="root",
    sha256_checksum="2e263d... (dummy)"
)

TEMPLATES = [alpine_3_20]
