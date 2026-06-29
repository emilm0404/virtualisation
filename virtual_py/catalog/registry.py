from typing import List, Optional, Dict
from .models import OSTemplate

class CatalogRegistry:
    def __init__(self):
        self._templates: Dict[str, OSTemplate] = {}
        
        import os
        import json
        scraped_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scraped_catalog.json")
        if os.path.exists(scraped_path):
            try:
                with open(scraped_path, "r", encoding="utf-8") as f:
                    self._scraped_links = json.load(f)
            except Exception:
                self._scraped_links = {}
        else:
            self._scraped_links = {}

    def register(self, template: OSTemplate) -> None:
        """Registers a new OS template in the catalog."""
        if template.id in self._scraped_links:
            template.url = self._scraped_links[template.id]
            template.available = True
        self._templates[template.id] = template

    def get(self, template_id: str) -> Optional[OSTemplate]:
        """Retrieves a specific OS template by ID."""
        return self._templates.get(template_id)

    def list_all(self) -> List[OSTemplate]:
        """Lists all registered OS templates."""
        return list(self._templates.values())

# global default registry instance.
default_registry = CatalogRegistry()
