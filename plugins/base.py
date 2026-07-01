"""Abstract base class for all data-source plugins."""

from abc import ABC, abstractmethod
from typing import List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Component


class PluginBase(ABC):
    name: str = "base"

    @abstractmethod
    def setup(self) -> None:
        ...

    @abstractmethod
    def scrape_category(self, category_slug: str, *, max_pages: Optional[int] = None) -> List[Component]:
        ...

    @abstractmethod
    def teardown(self) -> None:
        ...

    def __repr__(self):
        return f"<Plugin: {self.name}>"
