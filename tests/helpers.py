from datetime import UTC, datetime

from news.models import ArticleEnrichment
from tests.factories import ArticleFactory


def at(year, month, day, hour=12):
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def make_enriched_article(
    topic="world", label="positive", score=0.5, published_at=None, enriched=True
):
    kwargs = {}
    if published_at is not None:
        kwargs["published_at"] = published_at
    article = ArticleFactory(**kwargs)
    if enriched:
        ArticleEnrichment.objects.create(
            article=article,
            sentiment_label=label,
            sentiment_score=score,
            topic=topic,
        )
    return article
