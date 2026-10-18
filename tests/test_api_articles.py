from datetime import UTC, datetime

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from news.models import ArticleEnrichment
from tests.factories import ArticleFactory, SourceFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


def at(year, month, day, hour=12):
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def make_article(
    title="Headline",
    topic="world",
    label="positive",
    score=0.5,
    published_at=None,
    source=None,
    enriched=True,
):
    kwargs = {"title": title}
    if published_at is not None:
        kwargs["published_at"] = published_at
    if source is not None:
        kwargs["raw__source"] = source
    article = ArticleFactory(**kwargs)
    if enriched:
        ArticleEnrichment.objects.create(
            article=article,
            sentiment_label=label,
            sentiment_score=score,
            topic=topic,
            summary="A summary.",
        )
    return article


def list_url():
    return reverse("article-list")


def titles(response):
    return [item["title"] for item in response.json()["results"]]


def test_api_root_lists_articles(api):
    response = api.get("/api/v1/")

    assert response.status_code == 200
    assert "articles" in response.json()


def test_list_is_paginated(api):
    for number in range(25):
        make_article(title=f"Story {number}", enriched=False)

    page_one = api.get(list_url()).json()
    page_two = api.get(list_url(), {"page": 2}).json()

    assert page_one["count"] == 25
    assert len(page_one["results"]) == 20
    assert page_one["next"] is not None
    assert page_one["previous"] is None
    assert len(page_two["results"]) == 5
    assert page_two["next"] is None


def test_page_size_can_be_chosen(api):
    for number in range(8):
        make_article(title=f"Story {number}", enriched=False)

    response = api.get(list_url(), {"page_size": 5})

    assert len(response.json()["results"]) == 5


def test_article_has_source_url_and_nested_enrichment(api):
    source = SourceFactory(name="BBC Test")
    article = make_article(
        title="Acme grows", topic="business", label="positive", score=0.7, source=source
    )

    data = api.get(list_url()).json()["results"][0]

    assert data["id"] == article.pk
    assert data["title"] == "Acme grows"
    assert data["url"] == article.url
    assert data["source"] == "BBC Test"
    assert data["enrichment"]["topic"] == "business"
    assert data["enrichment"]["sentiment_label"] == "positive"
    assert data["enrichment"]["sentiment_score"] == 0.7
    assert data["enrichment"]["summary"] == "A summary."


def test_article_without_enrichment_shows_null(api):
    make_article(title="Not analysed yet", enriched=False)

    data = api.get(list_url()).json()["results"][0]

    assert "enrichment" in data
    assert data["enrichment"] is None


def test_detail_endpoint(api):
    article = make_article(title="One article")

    response = api.get(reverse("article-detail", args=[article.pk]))

    assert response.status_code == 200
    assert response.json()["title"] == "One article"


def test_unknown_article_is_404(api):
    response = api.get(reverse("article-detail", args=[999999]))

    assert response.status_code == 404


def test_filter_by_topic(api):
    make_article(title="Match", topic="sports")
    make_article(title="Other", topic="world")

    response = api.get(list_url(), {"topic": "sports"})

    assert titles(response) == ["Match"]


def test_filter_by_sentiment_label(api):
    make_article(title="Good", label="positive")
    make_article(title="Bad", label="negative")

    response = api.get(list_url(), {"sentiment_label": "negative"})

    assert titles(response) == ["Bad"]


def test_filter_by_part_of_source_name(api):
    health = SourceFactory(name="BBC News - Health")
    business = SourceFactory(name="BBC News - Business")
    make_article(title="Health story", source=health)
    make_article(title="Business story", source=business)

    response = api.get(list_url(), {"source": "health"})

    assert titles(response) == ["Health story"]


def test_filters_can_be_combined(api):
    make_article(title="Both", topic="sports", label="negative")
    make_article(title="Wrong topic", topic="world", label="negative")
    make_article(title="Wrong label", topic="sports", label="positive")

    response = api.get(list_url(), {"topic": "sports", "sentiment_label": "negative"})

    assert titles(response) == ["Both"]


def test_published_date_filters_are_inclusive(api):
    make_article(title="Eleventh", published_at=at(2026, 10, 11))
    make_article(title="Twelfth", published_at=at(2026, 10, 12))
    make_article(title="Thirteenth", published_at=at(2026, 10, 13))

    after = api.get(list_url(), {"published_after": "2026-10-12"})
    before = api.get(list_url(), {"published_before": "2026-10-12"})
    both = api.get(
        list_url(), {"published_after": "2026-10-12", "published_before": "2026-10-12"}
    )

    assert set(titles(after)) == {"Twelfth", "Thirteenth"}
    assert set(titles(before)) == {"Eleventh", "Twelfth"}
    assert titles(both) == ["Twelfth"]


@pytest.mark.parametrize(
    "params",
    [
        {"topic": "cooking"},
        {"sentiment_label": "happy"},
        {"published_after": "not-a-date"},
        {"published_before": "2026-13-45"},
    ],
)
def test_invalid_filter_values_return_400(api, params):
    make_article()

    response = api.get(list_url(), params)

    assert response.status_code == 400


def test_search_matches_title_case_insensitively(api):
    make_article(title="Budget row deepens")
    make_article(title="Football final tonight")

    response = api.get(list_url(), {"search": "BUDGET"})

    assert titles(response) == ["Budget row deepens"]


def test_default_order_is_newest_first(api):
    make_article(title="Old", published_at=at(2026, 10, 10))
    make_article(title="New", published_at=at(2026, 10, 12))
    make_article(title="Middle", published_at=at(2026, 10, 11))

    response = api.get(list_url())

    assert titles(response) == ["New", "Middle", "Old"]


def test_ordering_can_be_changed(api):
    make_article(title="Old", published_at=at(2026, 10, 10), score=0.9)
    make_article(title="New", published_at=at(2026, 10, 12), score=-0.9)

    by_date = api.get(list_url(), {"ordering": "published_at"})
    by_score = api.get(list_url(), {"ordering": "enrichment__sentiment_score"})

    assert titles(by_date) == ["Old", "New"]
    assert titles(by_score) == ["New", "Old"]


def test_api_is_read_only(api):
    article = make_article()
    detail = reverse("article-detail", args=[article.pk])

    assert api.post(list_url(), {}).status_code == 405
    assert api.put(detail, {}).status_code == 405
    assert api.patch(detail, {}).status_code == 405
    assert api.delete(detail).status_code == 405


def test_list_uses_a_constant_number_of_queries(api, django_assert_max_num_queries):
    for number in range(10):
        make_article(title=f"Story {number}")

    # One query to count, one to fetch articles with source and enrichment joined in.
    with django_assert_max_num_queries(3):
        response = api.get(list_url())

    assert len(response.json()["results"]) == 10