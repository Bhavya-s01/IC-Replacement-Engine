"""Gap 13: Version-aware protocol matching (USB 3.0 vs 3.1 etc)."""

import re

VERSION_PROTOCOLS = {
    "USB": {
        "versions": ["1.0", "1.1", "2.0", "3.0", "3.1", "3.2", "4.0"],
        "backward_compatible": True,
    },
    "HDMI": {
        "versions": ["1.0", "1.1", "1.2", "1.3", "1.4", "2.0", "2.1"],
        "backward_compatible": True,
    },
    "DisplayPort": {
        "versions": ["1.0", "1.1", "1.2", "1.3", "1.4", "2.0", "2.1"],
        "backward_compatible": True,
    },
    "PCIe": {
        "versions": ["1.0", "2.0", "3.0", "4.0", "5.0", "6.0"],
        "backward_compatible": True,
    },
}


def extract_protocol_version(spec_string):
    if not spec_string:
        return None, None
    spec_upper = spec_string.upper()
    for proto_name in VERSION_PROTOCOLS:
        if proto_name.upper() in spec_upper:
            version_match = re.search(
                r"(\d+\.\d+|\d+)",
                spec_string[spec_upper.index(proto_name.upper()) + len(proto_name):]
            )
            if version_match:
                ver = version_match.group(1)
                if "." not in ver:
                    ver = ver + ".0"
                return proto_name, ver
            return proto_name, None
    return None, None


def protocols_compatible(target_spec, candidate_spec):
    """Returns (is_compatible, match_quality, score_multiplier)."""
    t_proto, t_ver = extract_protocol_version(target_spec)
    c_proto, c_ver = extract_protocol_version(candidate_spec)

    if not t_proto and not c_proto:
        t_lower = (target_spec or "").lower()
        c_lower = (candidate_spec or "").lower()
        if t_lower == c_lower:
            return True, "exact", 1.0
        if t_lower in c_lower or c_lower in t_lower:
            return True, "partial", 0.7
        return False, "different", 0.0

    if t_proto and c_proto and t_proto != c_proto:
        return False, "different_protocol", 0.0

    if t_proto == c_proto:
        if not t_ver or not c_ver:
            return True, "partial_version", 0.7
        if t_ver == c_ver:
            return True, "exact_version", 1.0

        proto_info = VERSION_PROTOCOLS.get(t_proto, {})
        versions = proto_info.get("versions", [])
        if proto_info.get("backward_compatible") and versions:
            try:
                t_idx = versions.index(t_ver)
                c_idx = versions.index(c_ver)
                if c_idx >= t_idx:
                    return True, "higher_version", 0.95
                else:
                    return False, "lower_version", 0.3
            except ValueError:
                pass
        return False, "version_mismatch", 0.2

    return False, "unknown", 0.5