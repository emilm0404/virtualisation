import sys
from typing import Optional
from virtual_py.core.interfaces import VMProvider

def get_provider(provider_type: Optional[str] = None, **kwargs) -> VMProvider:
    if provider_type is None:
        if sys.platform == "win32":
            provider_type = "hyperv"
        elif sys.platform.startswith("linux"):
            provider_type = "kvm"
        else:
            raise NotImplementedError(
                f"Unsupported platform '{sys.platform}'. Please specify provider_type='hyperv' or 'kvm' explicitly."
            )

    provider_type = provider_type.lower()
    if provider_type == "hyperv":
        from virtual_py.providers.hyperv import HyperVProvider
        return HyperVProvider(**kwargs)
    elif provider_type == "kvm":
        from virtual_py.providers.kvm import KVMProvider
        return KVMProvider(**kwargs)
    elif provider_type == "remote":
        from virtual_py.providers.remote import RemoteProvider
        return RemoteProvider(**kwargs)
    else:
        raise ValueError(f"Unknown VM provider type '{provider_type}'. Supported: 'hyperv', 'kvm', 'remote'.")
