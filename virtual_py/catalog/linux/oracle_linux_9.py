from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="oracle-linux-9",
    name="Oracle Linux 9.3",
    arch="x86_64",
    url="https://yum.oracle.com/ISOS/OracleLinux/OL9/u3/x86_64/OracleLinux-R9-U3-x86_64-boot.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
