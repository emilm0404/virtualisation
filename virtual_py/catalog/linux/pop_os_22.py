from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="pop-os-22",
    name="Pop!_OS 22.04 LTS",
    arch="x86_64",
    url="https://iso.pop-os.org/22.04/amd64/intel/pop-os_22.04_amd64_intel_33.iso",
    min_memory_mb=4096,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
