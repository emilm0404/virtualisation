from virtual_py.catalog.models import OSTemplate

win11_eval = OSTemplate(
    id="win11-eval",
    name="Windows 11 Enterprise Evaluation",
    arch="x86_64",
    url="https://go.microsoft.com/fwlink/p/?LinkID=2195514",
    min_memory_mb=4096,
    min_cpu_count=2,
    cloud_init_supported=False,
    default_username="Administrator"
)

TEMPLATES = [win11_eval]
