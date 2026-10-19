import json
from datetime import timedelta

import pytest
from django.utils import timezone

from news.models import Article, ArticleEnrichment
from pipeline.enrichment.llm_client import LLMUnavailableError
from pipeline.enrichment.prompts import PROMPT_VERSION
from pipeline.enrichment.service import enrich_pending
from tests.factories import ArticleFactory
from tests.fakes import FakeLLM, valid_reply

pytestmark = pytest.mark.django_db

DONE = Article.EnrichmentStatus.DONE
PENDING = Article.EnrichmentStatus.PENDING
FAILED = Article.EnrichmentStatus.FAILED


def test_valid_reply_creates_enrichment():
    article = ArticleFactory(title="Acme profits rise", description="Great results.")
    fake = FakeLLM([valid_reply()])

    stats = enrich_pending(fake, limit=10)

    article.refresh_from_db()
    enrichment = article.enrichment
    assert (stats.selected, stats.enriched, stats.failed) == (1, 1, 0)
    assert article.enrichment_status == DONE
    assert enrichment.sentiment_label == "positive"
    assert enrichment.sentiment_score == 0.6
    assert enrichment.topic == "business"
    assert enrichment.entities == ["Acme"]
    assert enrichment.summary == "Acme grew strongly."
    assert enrichment.model_name == "fake-model"
    assert enrichment.prompt_version == PROMPT_VERSION
    assert enrichment.input_tokens == 10
    assert enrichment.output_tokens == 5
    assert enrichment.vader_score is not None


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(valid_reply(), id="plain-json"),
        pytest.param(f"```json\n{valid_reply()}\n```", id="code-fence"),
        pytest.param(f"Sure! Here it is: {valid_reply()}", id="chatter-around-json"),
        pytest.param(valid_reply(sentiment="Positive"), id="capital-letters"),
    ],
)
def test_acceptable_replies_are_enriched(reply):
    article = ArticleFactory()

    stats = enrich_pending(FakeLLM([reply]), limit=10)

    article.refresh_from_db()
    assert stats.enriched == 1
    assert article.enrichment_status == DONE


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param("{not json", id="invalid-json"),
        pytest.param("I cannot help with that.", id="no-json-at-all"),
        pytest.param(valid_reply(score=1.7), id="score-too-high"),
        pytest.param(valid_reply(topic="cooking"), id="unknown-topic"),
        pytest.param(
            json.dumps({"sentiment": "positive", "score": 0.1, "topic": "world"}),
            id="missing-summary",
        ),
    ],
)
def test_unacceptable_replies_count_as_a_failed_attempt(reply):
    article = ArticleFactory()
    fake = FakeLLM([reply, reply])  # the classifier asks twice before giving up

    stats = enrich_pending(fake, limit=10)

    article.refresh_from_db()
    assert len(fake.calls) == 2
    assert stats.failed == 1
    assert stats.enriched == 0
    assert article.enrichment_attempts == 1
    assert article.enrichment_status == PENDING
    assert ArticleEnrichment.objects.count() == 0


def test_second_try_inside_one_attempt_can_succeed():
    article = ArticleFactory()
    fake = FakeLLM(["not json", valid_reply()])

    stats = enrich_pending(fake, limit=10)

    article.refresh_from_db()
    assert stats.enriched == 1
    assert article.enrichment_attempts == 0
    assert stats.input_tokens == 20  # both calls are counted


def test_third_failure_marks_article_failed():
    article = ArticleFactory(enrichment_attempts=2)

    stats = enrich_pending(FakeLLM(["bad", "bad"]), limit=10)

    article.refresh_from_db()
    assert article.enrichment_attempts == 3
    assert article.enrichment_status == FAILED
    assert stats.marked_failed == 1


def test_failures_accumulate_across_runs_then_article_is_left_alone():
    article = ArticleFactory()

    for expected_attempts in (1, 2, 3):
        enrich_pending(FakeLLM(["bad", "bad"]), limit=10)
        article.refresh_from_db()
        assert article.enrichment_attempts == expected_attempts

    assert article.enrichment_status == FAILED
    fake = FakeLLM()
    stats = enrich_pending(fake, limit=10)
    assert stats.selected == 0
    assert fake.calls == []


def test_enriched_article_is_never_sent_to_llm_again():
    ArticleFactory()
    enrich_pending(FakeLLM(default=valid_reply()), limit=10)

    fake = FakeLLM()
    stats = enrich_pending(fake, limit=10)

    assert stats.selected == 0
    assert fake.calls == []
    assert ArticleEnrichment.objects.count() == 1


def test_done_failed_and_exhausted_articles_are_never_selected():
    ArticleFactory(enrichment_status=DONE)
    ArticleFactory(enrichment_status=FAILED, enrichment_attempts=3)
    ArticleFactory(enrichment_status=PENDING, enrichment_attempts=3)
    fake = FakeLLM()

    stats = enrich_pending(fake, limit=10)

    assert stats.selected == 0
    assert fake.calls == []


def test_limit_is_respected_and_newest_articles_come_first():
    now = timezone.now()
    old = ArticleFactory(published_at=now - timedelta(days=2))
    newest = ArticleFactory(published_at=now)
    middle = ArticleFactory(published_at=now - timedelta(days=1))

    stats = enrich_pending(FakeLLM(default=valid_reply()), limit=2)

    for article in (old, newest, middle):
        article.refresh_from_db()
    assert stats.enriched == 2
    assert newest.enrichment_status == DONE
    assert middle.enrichment_status == DONE
    assert old.enrichment_status == PENDING


def test_one_bad_article_does_not_stop_the_rest():
    now = timezone.now()
    bad = ArticleFactory(published_at=now)  # newest, so it is processed first
    good = ArticleFactory(published_at=now - timedelta(hours=1))
    fake = FakeLLM(["bad", "bad", valid_reply()])

    stats = enrich_pending(fake, limit=10)

    bad.refresh_from_db()
    good.refresh_from_db()
    assert (stats.failed, stats.enriched) == (1, 1)
    assert bad.enrichment_attempts == 1
    assert good.enrichment_status == DONE


def test_llm_down_stops_run_without_counting_attempts():
    now = timezone.now()
    first = ArticleFactory(published_at=now)
    second = ArticleFactory(published_at=now - timedelta(hours=1))
    fake = FakeLLM([LLMUnavailableError("down")])

    stats = enrich_pending(fake, limit=10)

    first.refresh_from_db()
    second.refresh_from_db()
    assert stats.aborted is True
    assert stats.enriched == 0
    assert len(fake.calls) == 1  # the run stopped, it did not try the second article
    assert first.enrichment_attempts == 0
    assert second.enrichment_attempts == 0
    assert first.enrichment_status == PENDING
    assert "LLM unavailable" in stats.errors[0]


def test_token_totals_are_added_up():
    ArticleFactory()
    ArticleFactory()

    stats = enrich_pending(FakeLLM(default=valid_reply()), limit=10)

    assert stats.input_tokens == 20
    assert stats.output_tokens == 10


def test_sleep_happens_between_articles_only(monkeypatch):
    slept = []
    monkeypatch.setattr("pipeline.enrichment.service.time.sleep", slept.append)
    ArticleFactory()
    ArticleFactory()

    enrich_pending(FakeLLM(default=valid_reply()), limit=10, sleep_seconds=0.5)

    assert slept == [0.5]  # two articles means one pause
