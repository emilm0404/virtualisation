from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="photon-os",
    name="VMware Photon OS",
    arch="x86_64",
    url="https://packages.vmware.com/photon/5.0/Rev1/iso/photon-5.0-dde71ec57.x86_64.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
