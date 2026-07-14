"""Gap 9: Package/footprint compatibility scoring."""

FOOTPRINT_GROUPS = {
    "SOT-23-5": ["SOT-23-5", "SC-74A", "SOT-753", "SC-74", "SOT-23-5L"],
    "SOT-23-6": ["SOT-23-6", "SC-74-6", "SOT-457", "TSOT-23-6"],
    "SOT-23-3": ["SOT-23-3", "SOT-23", "SC-59", "SOT-346"],
    "SOIC-8": ["SOIC-8", "SO-8", "SOP-8", "8-SOIC"],
    "SOIC-16": ["SOIC-16", "SO-16", "SOP-16", "16-SOIC"],
    "QFN-8": ["QFN-8", "8-QFN", "DFN-8", "8-DFN", "8-WDFN", "8-UDFN"],
    "QFN-16": ["QFN-16", "16-QFN", "DFN-16", "16-DFN"],
    "QFN-24": ["QFN-24", "24-QFN", "24-WQFN"],
    "QFN-32": ["QFN-32", "32-QFN", "32-WQFN"],
    "QFN-48": ["QFN-48", "48-QFN", "48-WQFN"],
    "LQFP-48": ["LQFP-48", "48-LQFP", "TQFP-48", "48-TQFP"],
    "LQFP-64": ["LQFP-64", "64-LQFP", "TQFP-64"],
    "TSSOP-8": ["TSSOP-8", "8-TSSOP", "MSOP-8"],
    "TSSOP-16": ["TSSOP-16", "16-TSSOP"],
}

_PKG_TO_GROUP = {}
for group_name, variants in FOOTPRINT_GROUPS.items():
    for variant in variants:
        _PKG_TO_GROUP[variant.lower()] = group_name


def score_package_compatibility(target_pkg, candidate_pkg, max_weight=8.0):
    """Score package compatibility between target and candidate."""
    if not target_pkg or not candidate_pkg:
        return max_weight * 0.3

    a = target_pkg.strip().lower()
    b = candidate_pkg.strip().lower()

    if a == b:
        return max_weight

    group_a = _PKG_TO_GROUP.get(a)
    group_b = _PKG_TO_GROUP.get(b)
    if group_a and group_b and group_a == group_b:
        return max_weight * 0.95

    family_a = a.split("-")[0].replace(" ", "")
    family_b = b.split("-")[0].replace(" ", "")
    if family_a == family_b:
        return max_weight * 0.5

    return 0.0