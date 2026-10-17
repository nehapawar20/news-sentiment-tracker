from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.models import Article
from pipeline.enrichment.llm_client import LLMUnavailableError
from pipeline.management.commands import enrich_articles as enrich_cmd
from pipeline.models import PipelineRun
from tests.factories import ArticleFactory
from tests.fakes import FakeLLM, valid_reply

pytestmark = pytest.mark.django_db


@pytest.fixture
def use_fake(monkeypatch):
    """Make the command use a fake LLM instead of the real one."""

    def install(fake):
        monkeypatch.setattr(enrich_cmd.Command, "build_client", lambda self: fake)
        return fake

    return install


def run_command(**options):
    out = StringIO()
    call_command("enrich_articles", stdout=out, **options)
    return out.getvalue()


def get_run():
    return PipelineRun.objects.get(stage=PipelineRun.Stage.ENRICH)


def test_successful_run_is_recorded(use_fake):
    ArticleFactory()
    ArticleFactory()
    use_fake(FakeLLM(default=valid_reply()))

    output = run_command()

    run = get_run()
    assert run.status == PipelineRun.Status.SUCCESS
    assert (run.records_in, run.records_out, run.records_failed) == (2, 2, 0)
    assert run.finished_at is not None
    assert "success" in output


def test_mixed_run_is_partial(use_fake):
    ArticleFactory()
    ArticleFactory()
    use_fake(FakeLLM(["bad", "bad", valid_reply()]))

    run_command()

    run = get_run()
    assert run.status == PipelineRun.Status.PARTIAL
    assert (run.records_out, run.records_failed) == (1, 1)
    assert "article" in run.error_message


def test_run_where_everything_fails_is_failed(use_fake):
    ArticleFactory()
    use_fake(FakeLLM(["bad", "bad"]))

    run_command()

    assert get_run().status == PipelineRun.Status.FAILED


def test_llm_down_after_some_success_is_partial(use_fake):
    ArticleFactory()
    ArticleFactory()
    use_fake(FakeLLM([valid_reply(), LLMUnavailableError("down")]))

    run_command()

    run = get_run()
    assert run.status == PipelineRun.Status.PARTIAL
    assert "LLM unavailable" in run.error_message


def test_llm_down_from_the_start_is_failed_and_keeps_attempts(use_fake):
    article = ArticleFactory()
    use_fake(FakeLLM([LLMUnavailableError("down")]))

    run_command()

    article.refresh_from_db()
    assert get_run().status == PipelineRun.Status.FAILED
    assert article.enrichment_attempts == 0


def test_dry_run_calls_no_llm_and_records_nothing(use_fake):
    ArticleFactory(title="Some headline")
    fake = use_fake(FakeLLM())

    output = run_command(dry_run=True)

    assert "Dry run: 1 article(s)" in output
    assert "Some headline" in output
    assert fake.calls == []
    assert PipelineRun.objects.count() == 0
    assert Article.objects.get().enrichment_status == Article.EnrichmentStatus.PENDING


def test_limit_option_restricts_the_batch(use_fake):
    for _ in range(3):
        ArticleFactory()
    use_fake(FakeLLM(default=valid_reply()))

    run_command(limit=1)

    run = get_run()
    assert (run.records_in, run.records_out) == (1, 1)


def test_invalid_limit_is_rejected(use_fake):
    use_fake(FakeLLM())

    with pytest.raises(CommandError):
        run_command(limit=0)


def test_running_twice_does_not_reprocess(use_fake):
    ArticleFactory()
    fake = use_fake(FakeLLM(default=valid_reply()))

    run_command()
    calls_after_first_run = len(fake.calls)
    run_command()

    runs = PipelineRun.objects.filter(stage=PipelineRun.Stage.ENRICH).order_by(
        "started_at"
    )
    assert len(fake.calls) == calls_after_first_run
    assert [run.records_in for run in runs] == [1, 0]