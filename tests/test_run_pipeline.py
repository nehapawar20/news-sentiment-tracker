from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from pipeline.management.commands import run_pipeline as run_cmd
from pipeline.models import PipelineRun

pytestmark = pytest.mark.django_db

STAGE_OF = {
    "fetch_articles": "extract",
    "transform_articles": "transform",
    "enrich_articles": "enrich",
    "aggregate_daily": "aggregate",
}
ALL_STAGES = list(STAGE_OF)


class FakeStages:
    """Stands in for call_command inside run_pipeline.

    Records every call and creates the PipelineRun a real stage would create.
    An outcome can be a status string, an Exception to raise, or "no-record".
    """

    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    def __call__(self, name, *args, **options):
        self.calls.append((name, options))
        outcome = self.outcomes.get(name, "success")
        if isinstance(outcome, Exception):
            raise outcome
        if outcome != "no-record":
            PipelineRun.objects.create(stage=STAGE_OF[name], status=outcome)

    @property
    def names(self):
        return [name for name, _options in self.calls]

    def options_for(self, name):
        return dict(self.calls)[name]


@pytest.fixture
def stages(monkeypatch):
    def install(**outcomes):
        fake = FakeStages(outcomes)
        monkeypatch.setattr(run_cmd, "call_command", fake)
        return fake

    return install


def run(**options):
    out = StringIO()
    call_command("run_pipeline", stdout=out, **options)
    return out.getvalue()


def test_all_stages_run_in_order(stages):
    fake = stages()

    run()

    assert fake.names == ALL_STAGES


def test_summary_lists_every_stage(stages):
    stages()

    output = run()

    for name in ALL_STAGES:
        assert name in output
    assert "Pipeline summary" in output


def test_partial_stage_is_a_warning_and_the_run_continues(stages):
    fake = stages(fetch_articles="partial")

    output = run()  # no error, so the exit code would be 0

    assert fake.names == ALL_STAGES
    assert "partial" in output


def test_failed_fetch_stops_the_run(stages):
    fake = stages(fetch_articles="failed")

    with pytest.raises(CommandError, match="fetch_articles"):
        run()

    assert fake.names == ["fetch_articles"]


def test_fetch_that_raises_stops_the_run(stages):
    fake = stages(fetch_articles=CommandError("No matching active sources found."))

    with pytest.raises(CommandError, match="fetch_articles"):
        run()

    assert fake.names == ["fetch_articles"]


def test_crashing_transform_stops_before_enrich_and_aggregate(stages):
    fake = stages(transform_articles=RuntimeError("boom"))

    with pytest.raises(CommandError, match="transform_articles"):
        run()

    assert fake.names == ["fetch_articles", "transform_articles"]


def test_failed_enrich_still_lets_aggregate_run_but_reports_failure(stages):
    fake = stages(enrich_articles="failed")

    with pytest.raises(CommandError, match="enrich_articles"):
        run()

    assert fake.names == ALL_STAGES


def test_crashing_enrich_still_lets_aggregate_run(stages):
    fake = stages(enrich_articles=RuntimeError("Ollama is down"))

    with pytest.raises(CommandError, match="enrich_articles"):
        run()

    assert fake.names == ALL_STAGES


def test_failed_aggregate_is_reported(stages):
    stages(aggregate_daily="failed")

    with pytest.raises(CommandError, match="aggregate_daily"):
        run()


def test_every_failing_stage_is_named_in_the_error(stages):
    stages(enrich_articles="failed", aggregate_daily=RuntimeError("boom"))

    with pytest.raises(CommandError) as error:
        run()

    assert "enrich_articles" in str(error.value)
    assert "aggregate_daily" in str(error.value)


def test_stage_that_records_no_run_counts_as_failed(stages):
    stages(fetch_articles="no-record")

    with pytest.raises(CommandError, match="fetch_articles"):
        run()


def test_old_failed_runs_do_not_confuse_the_status_check(stages):
    PipelineRun.objects.create(stage="extract", status="failed")
    fake = stages()  # every stage succeeds this time

    run()

    assert fake.names == ALL_STAGES


def test_skip_enrich_leaves_out_only_the_llm_stage(stages):
    fake = stages()

    output = run(skip_enrich=True)

    assert fake.names == ["fetch_articles", "transform_articles", "aggregate_daily"]
    assert "skipped" in output


def test_options_are_passed_to_the_stages(stages):
    fake = stages()

    run(enrich_limit=5, enrich_sleep=1.5, days=7)

    assert fake.options_for("enrich_articles")["limit"] == 5
    assert fake.options_for("enrich_articles")["sleep"] == 1.5
    assert fake.options_for("aggregate_daily")["days"] == 7


def test_default_options(stages):
    fake = stages()

    run()

    assert fake.options_for("enrich_articles")["limit"] == 20
    assert fake.options_for("aggregate_daily")["days"] == 3


@pytest.mark.parametrize("options", [{"enrich_limit": 0}, {"days": 0}])
def test_invalid_options_are_rejected_before_anything_runs(stages, options):
    fake = stages()

    with pytest.raises(CommandError):
        run(**options)

    assert fake.calls == []


def test_tests_do_not_write_to_the_real_log_file():
    import logging
    from logging.handlers import RotatingFileHandler

    handlers = logging.getLogger("pipeline").handlers

    assert not any(isinstance(handler, RotatingFileHandler) for handler in handlers)
