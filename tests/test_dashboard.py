from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from news.models import ArticleEnrichment, DailyTopicSentiment
from tests.helpers import at, make_enriched_article

pytestmark = pytest.mark.django_db


def static_path(name):
    path = finders.find(name)
    assert path, f"{name} was not found by Django's static file finders"
    return Path(path)


def js_source():
    return static_path("dashboard/dashboard.js").read_text(encoding="utf-8")


def test_dashboard_loads_on_an_empty_database(client):
    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert "dashboard/index.html" in [template.name for template in response.templates]


def test_dashboard_is_the_home_page(client):
    assert reverse("dashboard") == "/"


def test_dashboard_page_has_every_topic_option(client):
    html = client.get(reverse("dashboard")).content.decode()

    for value, _label in ArticleEnrichment.Topic.choices:
        assert f'value="{value}"' in html


def test_dashboard_page_has_charts_table_and_scripts(client):
    html = client.get(reverse("dashboard")).content.decode()

    for element_id in ("trend-chart", "topic-chart", "articles", "topic", "from", "to"):
        assert f'id="{element_id}"' in html
    assert "/static/dashboard/dashboard.js" in html
    assert "/static/dashboard/chart.umd.min.js" in html


def test_dashboard_is_read_only(client):
    assert client.post(reverse("dashboard")).status_code == 405


def test_static_files_exist():
    assert static_path("dashboard/dashboard.css").stat().st_size > 0
    assert static_path("dashboard/dashboard.js").stat().st_size > 0


def test_chartjs_is_saved_locally():
    assert static_path("dashboard/chart.umd.min.js").stat().st_size > 50_000


def test_javascript_never_uses_innerhtml():
    # Headlines come from other websites. textContent cannot run injected code.
    assert "innerHTML" not in js_source()
    assert "insertAdjacentHTML" not in js_source()
    assert "document.write" not in js_source()


def test_javascript_calls_every_api_endpoint_it_needs():
    source = js_source()

    for path in ('"/trends/"', '"/topics/"', '"/articles/"', '"/health/"'):
        assert path in source


def test_api_gives_the_fields_the_dashboard_reads(api):
    article = make_enriched_article(topic="world", label="negative", score=-0.4)
    DailyTopicSentiment.objects.create(
        date=at(2026, 10, 12).date(), topic="world", avg_sentiment=-0.4, article_count=1
    )

    trend = api.get(reverse("trends")).json()[0]
    topic = api.get(reverse("topics")).json()[0]
    row = api.get(reverse("article-list")).json()["results"][0]
    health = api.get(reverse("health")).json()

    assert {"date", "topic", "avg_sentiment"} <= set(trend)
    assert {"topic", "positive_count", "neutral_count", "negative_count"} <= set(topic)
    assert {"title", "url", "source", "published_at", "enrichment"} <= set(row)
    assert {"topic", "sentiment_label", "sentiment_score"} <= set(row["enrichment"])
    assert row["url"] == article.url
    assert "last_successful_run" in health
