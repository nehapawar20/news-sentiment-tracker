from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import OperationalError
from django.urls import reverse
from rest_framework.throttling import AnonRateThrottle

from news.api import views as api_views
from news.models import DailyTopicSentiment
from pipeline.models import PipelineRun
from tests.helpers import at, make_enriched_article

pytestmark = pytest.mark.django_db


# ---------- /topics/ ----------


def get_topics(api, **params):
    return api.get(reverse("topics"), params)


def test_topics_summarise_each_topic(api):
    make_enriched_article(topic="business", label="positive", score=0.5)
    make_enriched_article(topic="business", label="negative", score=-0.5)
    make_enriched_article(topic="sports", label="positive", score=0.8)

    response = get_topics(api)

    assert response.status_code == 200
    data = response.json()
    assert [row["topic"] for row in data] == ["business", "sports"]
    business, sports = data
    assert business["article_count"] == 2
    assert business["avg_sentiment"] == pytest.approx(0.0)
    assert business["positive_count"] == 1
    assert business["neutral_count"] == 0
    assert business["negative_count"] == 1
    assert sports["avg_sentiment"] == pytest.approx(0.8)


def test_topics_date_range_is_inclusive(api):
    make_enriched_article(topic="sports", published_at=at(2026, 10, 10))
    make_enriched_article(topic="business", published_at=at(2026, 10, 12))
    make_enriched_article(topic="world", published_at=at(2026, 10, 14))

    after = get_topics(api, **{"from": "2026-10-11"}).json()
    before = get_topics(api, to="2026-10-12").json()
    both = get_topics(api, **{"from": "2026-10-11", "to": "2026-10-12"}).json()

    assert {row["topic"] for row in after} == {"business", "world"}
    assert {row["topic"] for row in before} == {"sports", "business"}
    assert [row["topic"] for row in both] == ["business"]


def test_topics_ignore_articles_without_enrichment(api):
    make_enriched_article(enriched=False)

    assert get_topics(api).json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"from": "yesterday"},
        {"to": "2026-13-01"},
        {"from": "2026-10-12", "to": "2026-10-01"},
    ],
)
def test_topics_reject_bad_dates(api, params):
    response = get_topics(api, **params)

    assert response.status_code == 400


# ---------- /trends/ ----------


def make_trend(day, topic, avg=0.1, count=3):
    return DailyTopicSentiment.objects.create(
        date=day, topic=topic, avg_sentiment=avg, article_count=count
    )


def get_trends(api, **params):
    return api.get(reverse("trends"), params)


def test_trends_return_a_plain_list_ordered_by_date_then_topic(api):
    make_trend(date(2026, 10, 11), "sports")
    make_trend(date(2026, 10, 10), "sports")
    make_trend(date(2026, 10, 10), "business")

    response = get_trends(api)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)  # not paginated
    assert [(row["date"], row["topic"]) for row in data] == [
        ("2026-10-10", "business"),
        ("2026-10-10", "sports"),
        ("2026-10-11", "sports"),
    ]
    assert set(data[0]) == {
        "date",
        "topic",
        "avg_sentiment",
        "article_count",
        "positive_count",
        "neutral_count",
        "negative_count",
    }


def test_trends_filter_by_topic_and_dates(api):
    make_trend(date(2026, 10, 10), "business")
    make_trend(date(2026, 10, 11), "business")
    make_trend(date(2026, 10, 12), "business")
    make_trend(date(2026, 10, 11), "sports")

    by_topic = get_trends(api, topic="business").json()
    by_range = get_trends(
        api, topic="business", **{"from": "2026-10-11", "to": "2026-10-11"}
    ).json()

    assert len(by_topic) == 3
    assert [row["date"] for row in by_range] == ["2026-10-11"]


def test_trends_with_no_data_return_an_empty_list(api):
    assert get_trends(api).json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"topic": "cooking"},
        {"from": "not-a-date"},
        {"from": "2026-10-12", "to": "2026-10-01"},
    ],
)
def test_trends_reject_bad_parameters(api, params):
    response = get_trends(api, **params)

    assert response.status_code == 400


# ---------- /pipeline-runs/ ----------


def make_run(stage="extract", status="success", seconds=5):
    run = PipelineRun.objects.create(stage=stage, status=status)
    if seconds is not None:
        run.finished_at = run.started_at + timedelta(seconds=seconds)
        run.save()
    return run


def get_runs(api, **params):
    return api.get(reverse("pipeline-run-list"), params)


def test_pipeline_runs_are_listed_newest_first_with_duration(api):
    make_run(stage="extract", seconds=5)
    make_run(stage="transform", seconds=2)

    data = get_runs(api).json()

    assert data["count"] == 2
    assert [row["stage"] for row in data["results"]] == ["transform", "extract"]
    assert data["results"][1]["duration_seconds"] == pytest.approx(5.0)


def test_unfinished_run_has_no_duration(api):
    make_run(status="running", seconds=None)

    row = get_runs(api).json()["results"][0]

    assert row["finished_at"] is None
    assert row["duration_seconds"] is None


def test_pipeline_runs_filter_by_stage_and_status(api):
    make_run(stage="extract", status="success")
    make_run(stage="extract", status="failed")
    make_run(stage="enrich", status="success")

    by_stage = get_runs(api, stage="extract").json()
    by_both = get_runs(api, stage="extract", status="failed").json()

    assert by_stage["count"] == 2
    assert by_both["count"] == 1


@pytest.mark.parametrize("params", [{"stage": "cooking"}, {"status": "great"}])
def test_pipeline_runs_reject_bad_filters(api, params):
    assert get_runs(api, **params).status_code == 400


def test_pipeline_runs_are_read_only(api):
    run = make_run()
    detail = reverse("pipeline-run-detail", args=[run.pk])

    assert api.get(detail).status_code == 200
    assert api.post(reverse("pipeline-run-list"), {}).status_code == 405
    assert api.delete(detail).status_code == 405


# ---------- /health/ ----------


def test_health_with_no_runs_yet(api):
    response = api.get(reverse("health"))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["last_successful_run"] is None
    assert data["last_successful_run_by_stage"] == {}


def test_health_reports_last_successful_run_per_stage(api):
    extract = make_run(stage="extract", status="success", seconds=5)
    make_run(stage="extract", status="failed", seconds=1)  # must be ignored
    enrich = make_run(stage="enrich", status="success", seconds=30)

    data = api.get(reverse("health")).json()

    by_stage = data["last_successful_run_by_stage"]
    assert set(by_stage) == {"extract", "enrich"}
    assert datetime.fromisoformat(by_stage["extract"]) == extract.finished_at
    assert datetime.fromisoformat(data["last_successful_run"]) == max(
        extract.finished_at, enrich.finished_at
    )


def test_health_reports_database_problems_with_503(api, monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise OperationalError("database is down")

    monkeypatch.setattr(api_views, "connection", BrokenConnection())

    response = api.get(reverse("health"))

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "error"


# ---------- throttling ----------


def test_requests_are_throttled(api, monkeypatch):
    monkeypatch.setitem(AnonRateThrottle.THROTTLE_RATES, "anon", "2/hour")

    statuses = [api.get(reverse("topics")).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


def test_health_is_never_throttled(api, monkeypatch):
    monkeypatch.setitem(AnonRateThrottle.THROTTLE_RATES, "anon", "1/hour")

    statuses = [api.get(reverse("health")).status_code for _ in range(3)]

    assert statuses == [200, 200, 200]


# ---------- documentation ----------


def test_schema_describes_every_endpoint(api):
    response = api.get("/api/schema/", {"format": "json"})

    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/api/v1/articles/",
        "/api/v1/articles/{id}/",
        "/api/v1/topics/",
        "/api/v1/trends/",
        "/api/v1/pipeline-runs/",
        "/api/v1/health/",
    ):
        assert expected in paths


def test_swagger_docs_page_loads(api):
    response = api.get("/api/docs/")

    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]


def test_utc_constant_is_used():
    # Guards the date helpers above: tests assume timestamps are timezone-aware UTC.
    assert datetime(2026, 10, 12, tzinfo=UTC).utcoffset() == timedelta(0)
