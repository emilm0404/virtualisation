from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="void-linux",
    name="Void Linux",
    arch="x86_64",
    url="https://repo-default.voidlinux.org/live/current/void-live-x86_64-20250202-base.iso",
    min_memory_mb=512,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
