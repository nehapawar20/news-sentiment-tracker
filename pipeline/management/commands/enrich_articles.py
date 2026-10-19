import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pipeline.enrichment.llm_client import LLMClient
from pipeline.enrichment.service import enrich_pending, pending_articles
from pipeline.models import PipelineRun

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Enrich pending articles with sentiment and topic using the local LLM."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of articles to process in this run (default 20).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which articles would be processed, without calling the LLM.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.0,
            help="Seconds to wait between articles (default 0).",
        )

    def build_client(self):
        return LLMClient()

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1:
            raise CommandError("--limit must be at least 1.")

        if options["dry_run"]:
            articles = list(pending_articles(limit))
            self.stdout.write(f"Dry run: {len(articles)} article(s) would be enriched.")
            for article in articles:
                self.stdout.write(f"  [{article.pk}] {article.title[:80]}")
            return

        run = PipelineRun.objects.create(stage=PipelineRun.Stage.ENRICH)
        stats = enrich_pending(self.build_client(), limit, options["sleep"])

        if stats.aborted:
            status = PipelineRun.Status.PARTIAL if stats.enriched else PipelineRun.Status.FAILED
        elif stats.failed == 0:
            status = PipelineRun.Status.SUCCESS
        elif stats.enriched == 0:
            status = PipelineRun.Status.FAILED
        else:
            status = PipelineRun.Status.PARTIAL

        run.status = status
        run.finished_at = timezone.now()
        run.records_in = stats.selected
        run.records_out = stats.enriched
        run.records_failed = stats.failed
        run.error_message = "\n".join(stats.errors[:20])
        run.save()

        logger.info(
            "Enrich finished: %d selected, %d enriched, %d failed, tokens in=%d out=%d",
            stats.selected,
            stats.enriched,
            stats.failed,
            stats.input_tokens,
            stats.output_tokens,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{status}: {stats.selected} selected, {stats.enriched} enriched, "
                f"{stats.failed} failed (tokens in={stats.input_tokens}, "
                f"out={stats.output_tokens})"
            )
        )
