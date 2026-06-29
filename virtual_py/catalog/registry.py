from typing import List, Optional, Dict
from .models import OSTemplate

class CatalogRegistry:
    def __init__(self):
        self._templates: Dict[str, OSTemplate] = {}

    def register(self, template: OSTemplate) -> None:
        """Registers a new OS template in the catalog."""
        self._templates[template.id] = template

    def get(self, template_id: str) -> Optional[OSTemplate]:
        """Retrieves a specific OS template by ID."""
        return self._templates.get(template_id)

    def list_all(self) -> List[OSTemplate]:
        """Lists all registered OS templates."""
        return list(self._templates.values())

# global default registry instance.
default_registry = CatalogRegistry()
