from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="alpinelinux-edge",
    name="Alpine Linux Edge",
    arch="x86_64",
    url="https://dl-cdn.alpinelinux.org/alpine/edge/releases/x86_64/alpine-virt-edge-x86_64.iso",
    min_memory_mb=256,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
