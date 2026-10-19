from pathlib import Path

import pytest
import requests
import responses
from django.core.management import call_command

from news.models import RawArticle
from pipeline.extractors.rss import RSSExtractor
from pipeline.loaders import load_raw_articles
from pipeline.models import PipelineRun
from tests.factories import SourceFactory

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


def feed_xml() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def serve_feed(source):
    responses.add(
        responses.GET,
        source.feed_url,
        body=feed_xml(),
        status=200,
        content_type="application/rss+xml",
    )


@responses.activate
def test_extractor_returns_expected_items():
    source = SourceFactory()
    serve_feed(source)

    items = RSSExtractor().fetch(source)

    assert len(items) == 3
    assert items[0]["title"] == "First story"
    assert items[0]["summary"] == "Summary of the first story."


@responses.activate
def test_tracking_parameters_are_removed_from_url():
    source = SourceFactory()
    serve_feed(source)

    items = RSSExtractor().fetch(source)

    assert items[0]["url"] == "https://example.com/news/story-one"


@responses.activate
def test_missing_date_does_not_crash():
    source = SourceFactory()
    serve_feed(source)

    items = RSSExtractor().fetch(source)

    assert items[0]["published"] == "2026-10-12T05:00:52+00:00"
    assert items[2]["published"] is None


@responses.activate
def test_loader_twice_creates_no_duplicates():
    source = SourceFactory()
    serve_feed(source)
    items = RSSExtractor().fetch(source)

    first = load_raw_articles(source, items)
    second = load_raw_articles(source, items)

    assert first == 3
    assert second == 0
    assert RawArticle.objects.count() == 3


@responses.activate
def test_http_error_raises():
    source = SourceFactory()
    responses.add(responses.GET, source.feed_url, status=500)

    with pytest.raises(requests.RequestException):
        RSSExtractor().fetch(source)


@responses.activate
def test_not_found_raises_http_error():
    source = SourceFactory()
    responses.add(responses.GET, source.feed_url, status=404)

    with pytest.raises(requests.HTTPError):
        RSSExtractor().fetch(source)


@responses.activate
def test_command_survives_one_failing_source():
    good = SourceFactory(name="Good feed")
    bad = SourceFactory(name="Bad feed")
    serve_feed(good)
    responses.add(responses.GET, bad.feed_url, status=500)

    call_command("fetch_articles")

    run = PipelineRun.objects.get()
    assert run.status == PipelineRun.Status.PARTIAL
    assert run.records_failed == 1
    assert run.records_out == 3
    assert "Bad feed" in run.error_message
    assert RawArticle.objects.filter(source=good).count() == 3


@responses.activate
def test_command_run_twice_adds_no_duplicates():
    source = SourceFactory()
    serve_feed(source)

    call_command("fetch_articles")
    call_command("fetch_articles")

    runs = list(PipelineRun.objects.order_by("started_at"))
    assert runs[0].records_out == 3
    assert runs[1].records_out == 0
    assert RawArticle.objects.count() == 3


@responses.activate
def test_command_limit_option():
    source = SourceFactory()
    serve_feed(source)

    call_command("fetch_articles", limit=2)

    assert RawArticle.objects.count() == 2
