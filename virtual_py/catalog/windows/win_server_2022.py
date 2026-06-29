from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="win-server-2022",
    name="Windows Server 2022 Evaluation",
    arch="x86_64",
    url="https://go.microsoft.com/fwlink/p/?LinkID=2195167",
    min_memory_mb=4096,
    min_cpu_count=2,
    cloud_init_supported=False,
    default_username="Administrator"
)

TEMPLATES = [template]
