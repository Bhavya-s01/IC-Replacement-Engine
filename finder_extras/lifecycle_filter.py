"""Gap 18: Lifecycle-aware filtering at scrape and query time."""

EXCLUDE_STATUSES = {
    "obsolete", "discontinued", "not for new designs",
    "last time buy", "end of life", "eol",
}


def should_include_part(lifecycle_status, exclude_obsolete=True):
    if not exclude_obsolete:
        return True
    if not lifecycle_status:
        return True
    return lifecycle_status.strip().lower() not in EXCLUDE_STATUSES