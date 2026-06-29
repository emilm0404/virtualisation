from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="slackware",
    name="Slackware 15",
    arch="x86_64",
    url="https://mirrors.slackware.com/slackware/slackware-iso/slackware64-15.0-iso/slackware64-15.0-install-dvd.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
