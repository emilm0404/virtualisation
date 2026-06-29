from virtual_py.catalog.models import OSTemplate

ubuntu_24_04 = OSTemplate(
    id="ubuntu-24.04",
    name="Ubuntu 24.04 LTS (Noble Numbat) Server",
    arch="x86_64",
    url="https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="ubuntu"
)

TEMPLATES = [ubuntu_24_04]
