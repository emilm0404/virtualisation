from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="coreos",
    name="Fedora CoreOS",
    arch="x86_64",
    url="https://builds.coreos.fedoraproject.org/prod/streams/stable/builds/39.20240310.3.0/x86_64/fedora-coreos-39.20240310.3.0-live.x86_64.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
