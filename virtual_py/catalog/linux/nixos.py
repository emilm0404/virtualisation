from virtual_py.catalog.models import OSTemplate

template = OSTemplate(
    id="nixos",
    name="NixOS Minimal",
    arch="x86_64",
    url="https://releases.nixos.org/nixos/23.11/nixos-23.11.5540.35824e4d41fa/nixos-minimal-23.11.5540.35824e4d41fa-x86_64-linux.iso",
    min_memory_mb=1024,
    min_cpu_count=2,
    cloud_init_supported=True,
    default_username="root"
,
    available=False
)

TEMPLATES = [template]
