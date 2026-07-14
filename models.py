"""Data models for scraped IC components."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import json


@dataclass
class PriceBreak:
    quantity: int
    unit_price: float

    def to_dict(self):
        return {"quantity": self.quantity, "unit_price": self.unit_price}


@dataclass
class Component:
    manufacturer_part_number: str
    manufacturer: str
    digikey_part_number: str = ""
    description: str = ""
    category: str = ""
    subcategory: str = ""
    datasheet_url: str = ""
    product_url: str = ""
    stock: int = 0
    unit_price: float = 0.0
    price_breaks: List[PriceBreak] = field(default_factory=list)
    package: str = ""
    mounting_type: str = ""
    lifecycle_status: str = ""
    source: str = "digikey"
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    raw_specs: Dict[str, str] = field(default_factory=dict)
    substitutes: List[str] = field(default_factory=list)

    def price_breaks_json(self):
        if isinstance(self.price_breaks, str):
            return self.price_breaks
        if not self.price_breaks:
            return "[]"
        result = []
        for pb in self.price_breaks:
            if isinstance(pb, PriceBreak):
                result.append(pb.to_dict())
            elif isinstance(pb, dict):
                result.append(pb)
            else:
                result.append(str(pb))
        return json.dumps(result)

    def raw_specs_json(self):
        return json.dumps(self.raw_specs, ensure_ascii=False)

    def __repr__(self):
        return f"Component({self.manufacturer_part_number!r}, mfr={self.manufacturer!r}, cat={self.category!r})"
