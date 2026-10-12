import datetime

import pytest
from django.db import IntegrityError, transaction

from news.models import Article, DailyTopicSentiment, RawArticle
from tests.factories import ArticleFactory, RawArticleFactory, SourceFactory

pytestmark = pytest.mark.django_db


def test_create_raw_article():
    raw = RawArticleFactory()
    assert raw.pk is not None
    assert raw.status == RawArticle.Status.NEW
    assert RawArticle.objects.count() == 1


def test_duplicate_url_hash_is_rejected():
    first = RawArticleFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        RawArticleFactory(source=first.source, url_hash=first.url_hash)
    assert RawArticle.objects.count() == 1


def test_duplicate_source_feed_url_is_rejected():
    source = SourceFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        SourceFactory(feed_url=source.feed_url)


def test_article_belongs_to_raw_and_source():
    article = ArticleFactory()
    assert article.raw.article == article
    assert article.source == article.raw.source
    assert article.enrichment_status == Article.EnrichmentStatus.PENDING


def test_str_methods_are_readable():
    source = SourceFactory(name="BBC Test")
    raw = RawArticleFactory(source=source, url="https://example.com/a")
    article = ArticleFactory(title="Big news")
    assert str(source) == "BBC Test"
    assert "https://example.com/a" in str(raw)
    assert "new" in str(raw)
    assert str(article) == "Big news"


def test_daily_topic_sentiment_rejects_duplicate_date_and_topic():
    day = datetime.date(2026, 10, 12)
    DailyTopicSentiment.objects.create(
        date=day, topic="business", avg_sentiment=0.2, article_count=5
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        DailyTopicSentiment.objects.create(
            date=day, topic="business", avg_sentiment=0.5, article_count=2
        )
    assert DailyTopicSentiment.objects.count() == 1


def test_daily_topic_sentiment_allows_same_topic_on_different_days():
    DailyTopicSentiment.objects.create(
        date=datetime.date(2026, 10, 12), topic="business",
        avg_sentiment=0.1, article_count=3,
    )
    DailyTopicSentiment.objects.create(
        date=datetime.date(2026, 10, 13), topic="business",
        avg_sentiment=0.3, article_count=4,
    )
    assert DailyTopicSentiment.objects.count() == 2