import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_", "at_")
TRACKING_PARAMS = {"fbclid", "gclid", "ref", "ocid"}


def normalise_url(url: str) -> str:
    """Remove tracking parameters so the same article always has the same URL."""
    parts = urlsplit(url.strip())
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_PREFIXES)
        and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(kept), "")
    )


def make_url_hash(url: str) -> str:
    """A fixed-length fingerprint of a URL, used to detect duplicates."""
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()