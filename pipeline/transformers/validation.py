from .cleaning import normalize_title

MIN_TEXT_LENGTH = 20


def validate(title: str, description: str, url: str) -> str | None:
    """Return a rejection reason, or None if the record is acceptable."""
    if not normalize_title(title):
        return "empty_title"
    if not url.lower().startswith("http"):
        return "invalid_url"
    if len(f"{title} {description}".strip()) < MIN_TEXT_LENGTH:
        return "too_short"
    return None
