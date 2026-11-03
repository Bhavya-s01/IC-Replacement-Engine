"""Gap 1 & 5: Classify memory parts into correct subcategories."""

MEMORY_RULES = {
    "eeprom": {
        "keywords": ["eeprom", "electrically erasable"],
        "spec_hints": {"Memory Type": ["EEPROM"]},
    },
    "flash_memory": {
        "keywords": ["nor flash", "nand flash", "spi flash", "serial flash"],
        "spec_hints": {"Memory Type": ["Flash", "NOR", "NAND"]},
    },
    "fram_mram_sram": {
        "keywords": ["fram", "mram", "sram", "ferroelectric", "magnetoresistive"],
        "spec_hints": {"Memory Type": ["FRAM", "MRAM", "SRAM", "nvSRAM"]},
    },
}


def classify_memory_part(component):
    """Re-classify a part scraped from /memory/774 into the correct category."""
    desc = (component.description or "").lower()
    specs = component.raw_specs or {}

    for cat_slug, rules in MEMORY_RULES.items():
        for kw in rules["keywords"]:
            if kw in desc:
                return cat_slug
        for spec_name, values in rules["spec_hints"].items():
            spec_val = specs.get(spec_name, "").lower()
            for v in values:
                if v.lower() in spec_val:
                    return cat_slug

    return "flash_memory"

