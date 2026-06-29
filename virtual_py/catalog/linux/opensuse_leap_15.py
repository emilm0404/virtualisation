from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="opensuse-leap-15",
    name="openSUSE Leap 15.5",
    arch="x86_64",
    url="https://download.opensuse.org/distribution/leap/15.5/iso/./openSUSE-Leap-15.5-NET-x86_64-Build491.1-Media.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
