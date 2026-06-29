from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="mint-21",
    name="Linux Mint 21.3",
    arch="x86_64",
    url="https://mirrors.edge.kernel.org/linuxmint/stable/21.3/linuxmint-21.3-cinnamon-64bit.iso",
    min_memory_mb=2048,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
)

TEMPLATES = [template]
