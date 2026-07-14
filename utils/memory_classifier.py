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


def reclassify_memory_components(db):
    """Run after scraping /memory/774 to split parts into correct categories."""
    conn = db._get_conn()
    memory_slugs = ("eeprom", "flash_memory", "fram_mram_sram")
    placeholders = ",".join("?" for _ in memory_slugs)
    rows = conn.execute(
        "SELECT id, description, category FROM components WHERE category IN ({})".format(placeholders),
        memory_slugs
    ).fetchall()

    reclassified = 0
    for row in rows:
        comp_id = row["id"]
        specs_rows = conn.execute(
            "SELECT spec_name, spec_value FROM specifications WHERE component_id = ?",
            (comp_id,)
        ).fetchall()
        specs = {r["spec_name"]: r["spec_value"] for r in specs_rows}

        class FakeComp:
            pass
        fc = FakeComp()
        fc.description = row["description"]
        fc.raw_specs = specs

        new_category = classify_memory_part(fc)
        if new_category != row["category"]:
            conn.execute(
                "UPDATE components SET category = ? WHERE id = ?",
                (new_category, comp_id)
            )
            reclassified += 1

    conn.commit()
    return reclassified