import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import Source
from pipeline.extractors.rss import RSSExtractor
from pipeline.loaders import load_raw_articles
from pipeline.models import PipelineRun

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch articles from all active sources and store them as raw articles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", type=str, help="Only fetch the source with this exact name."
        )
        parser.add_argument("--limit", type=int, help="Keep at most this many entries per feed.")

    def handle(self, *args, **options):
        sources = Source.objects.filter(is_active=True)
        if options["source"]:
            sources = sources.filter(name=options["source"])
        sources = list(sources)
        if not sources:
            raise CommandError("No matching active sources found.")

        run = PipelineRun.objects.create(stage=PipelineRun.Stage.EXTRACT)
        extractor = RSSExtractor()
        total_in = total_new = failed_sources = 0
        errors = []

        for source in sources:
            try:
                items = extractor.fetch(source)
                if options["limit"]:
                    items = items[: options["limit"]]
                new_count = load_raw_articles(source, items)
                total_in += len(items)
                total_new += new_count
                logger.info("%s: %d fetched, %d new", source.name, len(items), new_count)
            except Exception as exc:  # one broken feed must not stop the others
                failed_sources += 1
                errors.append(f"{source.name}: {exc}")
                logger.exception("Failed to fetch %s", source.name)

        if failed_sources == 0:
            status = PipelineRun.Status.SUCCESS
        elif failed_sources == len(sources):
            status = PipelineRun.Status.FAILED
        else:
            status = PipelineRun.Status.PARTIAL

        run.status = status
        run.finished_at = timezone.now()
        run.records_in = total_in
        run.records_out = total_new
        run.records_failed = failed_sources
        run.error_message = "\n".join(errors)
        run.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"{status}: {total_in} fetched, {total_new} new, {failed_sources} source(s) failed."
            )
        )
