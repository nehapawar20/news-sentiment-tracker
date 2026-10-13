import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup


def strip_html(text: str) -> str:
    """Remove HTML tags and entities, and collapse extra whitespace."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def normalize_title(title: str) -> str:
    """Lowercase, drop punctuation and collapse spaces.

    Used to spot the same story published with slightly different punctuation.
    """
    if not title:
        return ""
    no_punctuation = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(no_punctuation.split())


def parse_published(entry: dict, fallback: datetime) -> datetime:
    """Return an aware UTC datetime for an entry, or `fallback` if the date is unusable."""
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=UTC)
        except (TypeError, ValueError):
            pass

    iso = entry.get("published")
    if iso:
        try:
            value = datetime.fromisoformat(iso)
        except (TypeError, ValueError):
            pass
        else:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

    return fallback