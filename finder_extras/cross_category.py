"""Gap 10: Cross-category alternative search."""

import logging

log = logging.getLogger(__name__)

RELATED_CATEGORIES = {
    "ldo_ic": ["dcdc_converter", "power_sequencer"],
    "dcdc_converter": ["ldo_ic"],
    "gate_driver": ["dcdc_converter", "display_driver"],
    "display_driver": ["gate_driver", "tcon_video"],
    "usb_ic": ["serial_interface", "video_interface"],
    "video_interface": ["usb_ic", "retimer_ic"],
    "retimer_ic": ["video_interface"],
    "flash_memory": ["eeprom", "fram_mram_sram"],
    "eeprom": ["flash_memory", "fram_mram_sram"],
    "fram_mram_sram": ["eeprom", "flash_memory"],
    "ambient_light": ["temp_sensor", "hall_sensor"],
    "temp_sensor": ["ambient_light"],
    "tcon_video": ["display_driver", "video_interface"],
    "audio_ic": ["opto_ic"],
    "battery_management": ["protection_ic", "power_sequencer"],
    "protection_ic": ["battery_management"],
    "serial_interface": ["usb_ic"],
    "clock_timing": ["mcu_soc"],
    "logic_mux": ["serial_interface"],
}


def get_related_categories(category_slug):
    return RELATED_CATEGORIES.get(category_slug, [])


def find_alternatives_cross_category(finder, target, top_n=10, min_compat=30.0):
    """
    Search for alternatives in the target's own category AND related categories.
    Related-category results get a 10% score penalty.
    """
    primary = finder.find_alternatives(
        target, top_n=top_n * 2, min_compatibility_pct=min_compat
    )

    related_slugs = get_related_categories(target.category)
    secondary = []

    for rel_cat in related_slugs:
        log.info("Cross-category search: %s -> %s", target.category, rel_cat)
        original_cat = target.category
        target.category = rel_cat
        try:
            results = finder.find_alternatives(
                target, top_n=top_n,
                same_category_only=True,
                min_compatibility_pct=min_compat * 0.8
            )
            for r in results:
                r.compatibility_pct *= 0.9
                r.total_score *= 0.9
            secondary.extend(results)
        finally:
            target.category = original_cat

    all_results = primary + secondary
    seen = set()
    unique = []
    for r in all_results:
        if r.mpn not in seen:
            seen.add(r.mpn)
            unique.append(r)

    unique.sort(key=lambda r: r.compatibility_pct, reverse=True)
    return unique[:top_n]