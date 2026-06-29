from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="kali-linux",
    name="Kali Linux",
    arch="x86_64",
    url="https://cdimage.kali.org/current/kali-linux-2026.2-installer-amd64.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
