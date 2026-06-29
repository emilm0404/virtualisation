from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="opensuse-tumbleweed",
    name="openSUSE Tumbleweed",
    arch="x86_64",
    url="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-NET-x86_64-Current.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
