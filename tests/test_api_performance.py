import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from news.models import DailyTopicSentiment
from pipeline.models import PipelineRun
from tests.helpers import at, make_enriched_article

pytestmark = pytest.mark.django_db


def count_queries(api, url, **params):
    with CaptureQueriesContext(connection) as context:
        response = api.get(url, params)
    assert response.status_code == 200
    return len(context)


def test_article_list_query_count_does_not_grow_with_data(api):
    for _ in range(2):
        make_enriched_article()
    few = count_queries(api, reverse("article-list"))

    for _ in range(18):
        make_enriched_article()
    many = count_queries(api, reverse("article-list"))

    assert many == few
    assert many <= 3  # one count, one data query


def test_article_detail_uses_few_queries(api):
    article = make_enriched_article()

    queries = count_queries(api, reverse("article-detail", args=[article.pk]))

    assert queries <= 2


def test_topics_query_count_does_not_grow_with_data(api):
    for _ in range(2):
        make_enriched_article()
    few = count_queries(api, reverse("topics"))

    for _ in range(18):
        make_enriched_article()
    many = count_queries(api, reverse("topics"))

    assert many == few
    assert many <= 2


def test_trends_query_count_does_not_grow_with_data(api):
    for day in range(1, 3):
        DailyTopicSentiment.objects.create(
            date=at(2026, 10, day).date(), topic="world", avg_sentiment=0.1
        )
    few = count_queries(api, reverse("trends"))

    for day in range(3, 21):
        DailyTopicSentiment.objects.create(
            date=at(2026, 10, day).date(), topic="world", avg_sentiment=0.1
        )
    many = count_queries(api, reverse("trends"))

    assert many == few
    assert many <= 2


def test_pipeline_run_list_query_count_does_not_grow_with_data(api):
    for _ in range(2):
        PipelineRun.objects.create(stage="extract", status="success")
    few = count_queries(api, reverse("pipeline-run-list"))

    for _ in range(18):
        PipelineRun.objects.create(stage="extract", status="success")
    many = count_queries(api, reverse("pipeline-run-list"))

    assert many == few
    assert many <= 3


def test_health_uses_few_queries(api):
    PipelineRun.objects.create(stage="extract", status="success")

    assert count_queries(api, reverse("health")) <= 3


def test_pipeline_runs_are_paginated(api):
    for _ in range(25):
        PipelineRun.objects.create(stage="extract", status="success")

    page_one = api.get(reverse("pipeline-run-list")).json()
    page_two = api.get(reverse("pipeline-run-list"), {"page": 2}).json()

    assert page_one["count"] == 25
    assert len(page_one["results"]) == 20
    assert len(page_two["results"]) == 5


def test_unknown_pipeline_run_is_404(api):
    response = api.get(reverse("pipeline-run-detail", args=[999999]))

    assert response.status_code == 404


def test_non_numeric_article_id_is_404(api):
    response = api.get("/api/v1/articles/not-a-number/")

    assert response.status_code == 404


def test_page_beyond_the_last_is_404(api):
    make_enriched_article()

    response = api.get(reverse("article-list"), {"page": 99})

    assert response.status_code == 404
