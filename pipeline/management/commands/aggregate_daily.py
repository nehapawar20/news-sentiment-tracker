import logging
from datetime import UTC, date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pipeline.aggregation import aggregate_day
from pipeline.models import PipelineRun

logger = logging.getLogger(__name__)

MAX_DAYS = 366


class Command(BaseCommand):
    help = "Compute daily topic sentiment from enriched articles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="Last day to compute, as YYYY-MM-DD (default: today, UTC).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="How many days to compute, ending at --date (default 1).",
        )

    def handle(self, *args, **options):
        if options["date"]:
            try:
                end = date.fromisoformat(options["date"])
            except ValueError as exc:
                raise CommandError("--date must look like 2026-10-12.") from exc
        else:
            end = datetime.now(UTC).date()

        days = options["days"]
        if not 1 <= days <= MAX_DAYS:
            raise CommandError(f"--days must be between 1 and {MAX_DAYS}.")

        day_list = [end - timedelta(days=offset) for offset in reversed(range(days))]

        run = PipelineRun.objects.create(stage=PipelineRun.Stage.AGGREGATE)
        total_articles = total_rows = failed_days = 0
        errors = []

        for day in day_list:
            try:
                result = aggregate_day(day)
            except Exception as exc:  # one bad day must not stop the others
                failed_days += 1
                errors.append(f"{day}: {exc}")
                logger.exception("Aggregation failed for %s", day)
                continue
            total_articles += result["articles"]
            total_rows += result["rows"]
            logger.info(
                "%s: %d articles, %d rows (%d created, %d updated, %d removed)",
                day,
                result["articles"],
                result["rows"],
                result["created"],
                result["updated"],
                result["deleted"],
            )

        if failed_days == 0:
            status = PipelineRun.Status.SUCCESS
        elif failed_days == len(day_list):
            status = PipelineRun.Status.FAILED
        else:
            status = PipelineRun.Status.PARTIAL

        run.status = status
        run.finished_at = timezone.now()
        run.records_in = total_articles
        run.records_out = total_rows
        run.records_failed = failed_days
        run.error_message = "\n".join(errors)
        run.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"{status}: {len(day_list)} day(s), {total_articles} articles, "
                f"{total_rows} topic rows, {failed_days} day(s) failed"
            )
        )