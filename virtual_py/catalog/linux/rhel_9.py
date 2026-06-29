from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="rhel-9",
    name="Red Hat Enterprise Linux 9.3",
    arch="x86_64",
    url="https://access.cdn.redhat.com/content/origin/files/rhel-9.3-x86_64-boot.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
