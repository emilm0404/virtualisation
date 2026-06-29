from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="win10-eval",
    name="Windows 10 Enterprise Evaluation",
    arch="x86_64",
    url="https://go.microsoft.com/fwlink/p/?LinkID=2195165",
    min_memory_mb=4096,
    min_cpu_count=2,
    cloud_init_supported=False,
    default_username="Administrator"
,
    available=False
)

TEMPLATES = [template]
