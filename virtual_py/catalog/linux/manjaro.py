from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="manjaro",
    name="Manjaro Linux",
    arch="x86_64",
    url="https://download.manjaro.org/kde/23.1.3/manjaro-kde-23.1.3-240113-linux66.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
