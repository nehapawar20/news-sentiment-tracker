import pytest
from django.core.management import call_command

from news.models import Article, RawArticle
from pipeline.management.commands import transform_articles as transform_cmd
from pipeline.models import PipelineRun
from tests.factories import RawArticleFactory

pytestmark = pytest.mark.django_db

GOOD_SUMMARY = "A sufficiently long summary of the story."


def make_raw(title="A perfectly good headline", summary=GOOD_SUMMARY, **extra):
    payload = {"title": title, "summary": summary}
    payload.update(extra.pop("payload_extra", {}))
    return RawArticleFactory(payload=payload, **extra)


def run_transform():
    call_command("transform_articles")


def test_valid_raw_record_becomes_article():
    raw = make_raw(
        title="<b>Markets</b> rise &amp; fall",
        summary="<p>Shares moved today.</p> More detail here.",
        payload_extra={"published": "2026-10-12T05:00:52+00:00"},
    )

    run_transform()

    article = Article.objects.get()
    raw.refresh_from_db()
    assert article.raw == raw
    assert article.title == "Markets rise & fall"
    assert article.description == "Shares moved today. More detail here."
    assert article.published_at.isoformat() == "2026-10-12T05:00:52+00:00"
    assert article.enrichment_status == Article.EnrichmentStatus.PENDING
    assert raw.status == RawArticle.Status.PROCESSED


def test_missing_date_falls_back_to_fetch_time():
    raw = make_raw()

    run_transform()

    raw.refresh_from_db()
    assert Article.objects.get().published_at == raw.fetched_at


def test_empty_title_is_rejected():
    raw = make_raw(title="   ")

    run_transform()

    raw.refresh_from_db()
    assert raw.status == RawArticle.Status.REJECTED
    assert raw.rejection_reason == "empty_title"
    assert Article.objects.count() == 0


def test_title_with_only_punctuation_is_rejected():
    raw = make_raw(title="!!!")

    run_transform()

    raw.refresh_from_db()
    assert raw.rejection_reason == "empty_title"


def test_too_short_text_is_rejected():
    raw = make_raw(title="Hi", summary="")

    run_transform()

    raw.refresh_from_db()
    assert raw.status == RawArticle.Status.REJECTED
    assert raw.rejection_reason == "too_short"


def test_invalid_url_is_rejected():
    raw = make_raw(url="ftp://example.com/story")

    run_transform()

    raw.refresh_from_db()
    assert raw.rejection_reason == "invalid_url"
    assert Article.objects.count() == 0


def test_duplicate_title_is_rejected():
    first = make_raw(title="Big News Today!")
    second = make_raw(title="big   news today")

    run_transform()

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == RawArticle.Status.PROCESSED
    assert second.status == RawArticle.Status.REJECTED
    assert second.rejection_reason == "duplicate_title"
    assert Article.objects.count() == 1


def test_running_twice_creates_nothing_new():
    make_raw(title="Story one is here")
    make_raw(title="Story two is here")

    run_transform()
    run_transform()

    assert Article.objects.count() == 2
    first_run, second_run = PipelineRun.objects.filter(stage=PipelineRun.Stage.TRANSFORM).order_by(
        "started_at"
    )
    assert first_run.records_out == 2
    assert second_run.records_in == 0
    assert second_run.records_out == 0


def test_pipeline_run_records_counts():
    make_raw(title="A good story here")
    make_raw(title="")
    make_raw(title="Another good story")

    run_transform()

    run = PipelineRun.objects.get(stage=PipelineRun.Stage.TRANSFORM)
    assert run.status == PipelineRun.Status.SUCCESS
    assert run.records_in == 3
    assert run.records_out == 2
    assert run.records_failed == 1


def test_unexpected_error_is_isolated(monkeypatch):
    real_strip_html = transform_cmd.strip_html

    def flaky_strip_html(text):
        if "BOOM" in text:
            raise ValueError("boom")
        return real_strip_html(text)

    monkeypatch.setattr(transform_cmd, "strip_html", flaky_strip_html)
    bad = make_raw(title="BOOM headline here")
    make_raw(title="A healthy headline")

    run_transform()

    bad.refresh_from_db()
    assert bad.status == RawArticle.Status.REJECTED
    assert bad.rejection_reason == "transform_error"
    assert Article.objects.count() == 1
    run = PipelineRun.objects.get(stage=PipelineRun.Stage.TRANSFORM)
    assert run.status == PipelineRun.Status.PARTIAL
