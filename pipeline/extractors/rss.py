import json
import logging
from datetime import UTC, datetime

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pipeline.utils import normalise_url

from .base import BaseExtractor

logger = logging.getLogger(__name__)

USER_AGENT = "NewsSentimentTracker/0.1 (learning project)"


class RSSExtractor(BaseExtractor):
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self, source) -> list[dict]:
        response = self.session.get(source.feed_url, timeout=self.timeout)
        response.raise_for_status()

        feed = feedparser.parse(response.content)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Could not parse feed: {source.feed_url}")

        items = []
        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                logger.warning("Skipping entry without link in %s", source.name)
                continue
            items.append(
                {
                    "url": normalise_url(link),
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "published": self._published_iso(entry),
                    "raw_entry": self._to_jsonable(entry),
                }
            )
        logger.info("Fetched %d entries from %s", len(items), source.name)
        return items

    @staticmethod
    def _published_iso(entry) -> str | None:
        parsed = entry.get("published_parsed")
        if not parsed:
            return None
        return datetime(*parsed[:6], tzinfo=UTC).isoformat()

    @staticmethod
    def _to_jsonable(entry) -> dict:
        # feedparser entries contain time tuples, which JSON cannot store directly.
        return json.loads(json.dumps(entry, default=str))
