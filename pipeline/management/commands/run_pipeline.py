import logging
import time
from dataclasses import dataclass

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max

from pipeline.models import PipelineRun

logger = logging.getLogger(__name__)

# (command name, the PipelineRun stage it records, stop the whole run if it fails?)
STAGES = [
    ("fetch_articles", PipelineRun.Stage.EXTRACT, True),
    ("transform_articles", PipelineRun.Stage.TRANSFORM, True),
    ("enrich_articles", PipelineRun.Stage.ENRICH, False),
    ("aggregate_daily", PipelineRun.Stage.AGGREGATE, False),
]


@dataclass
class StageResult:
    name: str
    status: str
    seconds: float


class Command(BaseCommand):
    help = (
        "Run every pipeline stage in order: fetch, transform, enrich, aggregate. "
        "Exits with an error if any stage failed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-enrich",
            action="store_true",
            help="Skip the LLM stage (useful when Ollama is not running).",
        )
        parser.add_argument(
            "--enrich-limit",
            type=int,
            default=20,
            help="Maximum articles to enrich in this run (default 20).",
        )
        parser.add_argument(
            "--enrich-sleep",
            type=float,
            default=0.0,
            help="Seconds to wait between enriched articles (default 0).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=3,
            help="Recompute the last N days of daily sentiment (default 3).",
        )

    def handle(self, *args, **options):
        if options["enrich_limit"] < 1:
            raise CommandError("--enrich-limit must be at least 1.")
        if options["days"] < 1:
            raise CommandError("--days must be at least 1.")

        logger.info("Pipeline run starting")
        results = []
        failed = []

        for name, stage, stop_on_failure in STAGES:
            if name == "enrich_articles" and options["skip_enrich"]:
                logger.info("Skipping %s (--skip-enrich)", name)
                results.append(StageResult(name, "skipped", 0.0))
                continue

            result = self.run_stage(name, stage, self.stage_options(name, options))
            results.append(result)

            if result.status == PipelineRun.Status.FAILED:
                failed.append(name)
                if stop_on_failure:
                    logger.error("Stopping the run: the later stages depend on %s", name)
                    break
            elif result.status == PipelineRun.Status.PARTIAL:
                logger.warning("Stage %s finished with warnings (partial)", name)

        self.print_summary(results)

        if failed:
            message = f"Pipeline finished with failures in: {', '.join(failed)}"
            logger.error(message)
            raise CommandError(message)
        logger.info("Pipeline run finished without failures")

    @staticmethod
    def stage_options(name, options):
        if name == "enrich_articles":
            return {"limit": options["enrich_limit"], "sleep": options["enrich_sleep"]}
        if name == "aggregate_daily":
            return {"days": options["days"]}
        return {}

    def run_stage(self, name, stage, stage_options) -> StageResult:
        # Remember the newest run id, so we only look at the run THIS call creates.
        last_id = PipelineRun.objects.filter(stage=stage).aggregate(last=Max("id"))["last"] or 0
        logger.info("Stage %s starting", name)
        started = time.monotonic()

        try:
            call_command(name, stdout=self.stdout, **stage_options)
        except CommandError as exc:
            logger.error("Stage %s refused to run: %s", name, exc)
            return StageResult(name, PipelineRun.Status.FAILED, time.monotonic() - started)
        except Exception:
            logger.exception("Stage %s crashed", name)
            return StageResult(name, PipelineRun.Status.FAILED, time.monotonic() - started)

        seconds = time.monotonic() - started
        run = PipelineRun.objects.filter(stage=stage, id__gt=last_id).order_by("-id").first()
        if run is None:
            logger.error("Stage %s did not record a pipeline run", name)
            return StageResult(name, PipelineRun.Status.FAILED, seconds)

        logger.info("Stage %s finished: %s in %.1fs", name, run.status, seconds)
        return StageResult(name, run.status, seconds)

    def print_summary(self, results):
        self.stdout.write("\nPipeline summary")
        for result in results:
            self.stdout.write(f"  {result.name:20} {result.status:8} {result.seconds:6.1f}s")
