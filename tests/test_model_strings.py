from datetime import date

import pytest

from news.models import ArticleEnrichment, DailyTopicSentiment
from pipeline.models import PipelineRun
from tests.factories import ArticleFactory

pytestmark = pytest.mark.django_db


def test_enrichment_string_is_readable():
    article = ArticleFactory()
    enrichment = ArticleEnrichment.objects.create(
        article=article, sentiment_label="positive", sentiment_score=0.5, topic="world"
    )

    assert str(enrichment) == f"{article.pk}: positive / world"


def test_daily_topic_sentiment_string_is_readable():
    row = DailyTopicSentiment.objects.create(
        date=date(2026, 10, 12), topic="business", avg_sentiment=0.25
    )

    assert str(row) == "2026-10-12 business: 0.25"


def test_pipeline_run_string_is_readable():
    run = PipelineRun.objects.create(stage="extract", status="success")

    assert str(run).startswith("extract success @ ")
