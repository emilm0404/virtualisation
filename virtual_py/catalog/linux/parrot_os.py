from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="parrot-os",
    name="Parrot OS Security",
    arch="x86_64",
    url="https://deb.parrot.sh/parrot/iso/current/Parrot-security-amd64.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
