from datetime import UTC, date, datetime
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.models import ArticleEnrichment, DailyTopicSentiment
from pipeline.aggregation import aggregate_day
from pipeline.management.commands import aggregate_daily as aggregate_cmd
from pipeline.models import PipelineRun
from tests.factories import ArticleFactory

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 12)


def make_enriched(published_at, topic="business", label="positive", score=0.5):
    article = ArticleFactory(published_at=published_at)
    ArticleEnrichment.objects.create(
        article=article,
        sentiment_label=label,
        sentiment_score=score,
        topic=topic,
    )
    return article


def at(day, hour=12, minute=0, second=0):
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)


def run_command(**options):
    out = StringIO()
    call_command("aggregate_daily", stdout=out, **options)
    return out.getvalue()


def test_counts_and_average_for_one_topic():
    make_enriched(at(DAY), label="positive", score=0.5)
    make_enriched(at(DAY), label="negative", score=-0.5)
    make_enriched(at(DAY), label="neutral", score=0.0)

    result = aggregate_day(DAY)

    row = DailyTopicSentiment.objects.get(date=DAY, topic="business")
    assert result["articles"] == 3
    assert row.article_count == 3
    assert row.avg_sentiment == pytest.approx(0.0)
    assert (row.positive_count, row.neutral_count, row.negative_count) == (1, 1, 1)


def test_one_row_per_topic():
    make_enriched(at(DAY), topic="business")
    make_enriched(at(DAY), topic="sports")
    make_enriched(at(DAY), topic="sports")

    aggregate_day(DAY)

    assert DailyTopicSentiment.objects.filter(date=DAY).count() == 2
    assert DailyTopicSentiment.objects.get(date=DAY, topic="sports").article_count == 2


def test_only_articles_of_that_utc_day_are_counted():
    make_enriched(at(DAY, 23, 59, 59))
    make_enriched(at(date(2026, 10, 13), 0, 0, 0))
    make_enriched(at(date(2026, 10, 11), 12))

    aggregate_day(DAY)
    aggregate_day(date(2026, 10, 13))

    assert DailyTopicSentiment.objects.get(date=DAY, topic="business").article_count == 1
    next_day = DailyTopicSentiment.objects.get(
        date=date(2026, 10, 13), topic="business"
    )
    assert next_day.article_count == 1


def test_day_without_articles_creates_nothing():
    result = aggregate_day(DAY)

    assert result["rows"] == 0
    assert DailyTopicSentiment.objects.count() == 0


def test_running_twice_creates_no_duplicates():
    make_enriched(at(DAY))

    first = aggregate_day(DAY)
    second = aggregate_day(DAY)

    assert (first["created"], first["updated"]) == (1, 0)
    assert (second["created"], second["updated"]) == (0, 1)
    assert DailyTopicSentiment.objects.count() == 1


def test_new_data_updates_the_existing_row():
    make_enriched(at(DAY), score=0.5)
    aggregate_day(DAY)
    make_enriched(at(DAY), label="negative", score=-0.5)

    aggregate_day(DAY)

    row = DailyTopicSentiment.objects.get()
    assert row.article_count == 2
    assert row.avg_sentiment == pytest.approx(0.0)


def test_stale_topic_row_is_removed():
    make_enriched(at(DAY), topic="business")
    DailyTopicSentiment.objects.create(
        date=DAY, topic="sports", avg_sentiment=0.9, article_count=4
    )

    result = aggregate_day(DAY)

    assert result["deleted"] == 1
    assert list(DailyTopicSentiment.objects.values_list("topic", flat=True)) == [
        "business"
    ]


def test_command_back_fills_several_days_and_records_the_run():
    make_enriched(at(date(2026, 10, 10)))
    make_enriched(at(date(2026, 10, 11)), topic="sports")
    make_enriched(at(date(2026, 10, 12)))

    output = run_command(date="2026-10-12", days=3)

    run = PipelineRun.objects.get(stage=PipelineRun.Stage.AGGREGATE)
    assert run.status == PipelineRun.Status.SUCCESS
    assert (run.records_in, run.records_out, run.records_failed) == (3, 3, 0)
    assert DailyTopicSentiment.objects.count() == 3
    assert "success" in output


def test_command_run_twice_gives_same_table():
    make_enriched(at(DAY))

    run_command(date="2026-10-12")
    run_command(date="2026-10-12")

    assert DailyTopicSentiment.objects.count() == 1
    assert PipelineRun.objects.filter(stage=PipelineRun.Stage.AGGREGATE).count() == 2


def test_invalid_date_is_rejected():
    with pytest.raises(CommandError):
        run_command(date="12/10/2026")


@pytest.mark.parametrize("days", [0, -1, 400])
def test_invalid_days_is_rejected(days):
    with pytest.raises(CommandError):
        run_command(date="2026-10-12", days=days)


def test_one_failing_day_does_not_stop_the_others(monkeypatch):
    make_enriched(at(date(2026, 10, 11)))
    make_enriched(at(date(2026, 10, 12)))
    real_aggregate_day = aggregate_cmd.aggregate_day

    def flaky(day):
        if day == date(2026, 10, 11):
            raise RuntimeError("boom")
        return real_aggregate_day(day)

    monkeypatch.setattr(aggregate_cmd, "aggregate_day", flaky)

    run_command(date="2026-10-12", days=2)

    run = PipelineRun.objects.get(stage=PipelineRun.Stage.AGGREGATE)
    assert run.status == PipelineRun.Status.PARTIAL
    assert run.records_failed == 1
    assert "2026-10-11" in run.error_message
    assert DailyTopicSentiment.objects.filter(date=date(2026, 10, 12)).exists()