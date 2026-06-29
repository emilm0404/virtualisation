from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="win-server-2019",
    name="Windows Server 2019 Evaluation",
    arch="x86_64",
    url="https://go.microsoft.com/fwlink/p/?LinkID=2195166",
    min_memory_mb=4096,
    min_cpu_count=2,
    cloud_init_supported=False,
    default_username="Administrator"
)

TEMPLATES = [template]
