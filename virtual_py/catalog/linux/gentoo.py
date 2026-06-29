from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="gentoo",
    name="Gentoo Minimal",
    arch="x86_64",
    url="https://distfiles.gentoo.org/releases/amd64/autobuilds/current-install-amd64-minimal/install-amd64-minimal-20260531T160106Z.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
