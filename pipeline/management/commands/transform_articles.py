import hashlib
import logging
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import Article, RawArticle
from pipeline.models import PipelineRun
from pipeline.transformers.cleaning import normalize_title, parse_published, strip_html
from pipeline.transformers.validation import validate

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


class Command(BaseCommand):
    help = "Clean new raw articles and turn them into Article rows."

    def handle(self, *args, **options):
        run = PipelineRun.objects.create(stage=PipelineRun.Stage.TRANSFORM)

        ids = list(
            RawArticle.objects.filter(status=RawArticle.Status.NEW)
            .order_by("id")
            .values_list("id", flat=True)
        )

        created = errors = 0
        rejected = Counter()

        for start in range(0, len(ids), BATCH_SIZE):
            batch_ids = ids[start : start + BATCH_SIZE]
            with transaction.atomic():
                raws = RawArticle.objects.filter(id__in=batch_ids).select_related(
                    "source"
                )
                for raw in raws.order_by("id"):
                    try:
                        with transaction.atomic():
                            reason = self.transform_one(raw)
                    except Exception:
                        logger.exception("Transform failed for raw article %s", raw.pk)
                        reason = "transform_error"
                        errors += 1
                        raw.status = RawArticle.Status.REJECTED
                        raw.rejection_reason = reason
                        raw.save(update_fields=["status", "rejection_reason"])
                    if reason is None:
                        created += 1
                    else:
                        rejected[reason] += 1

        rejected_total = sum(rejected.values())
        run.status = (
            PipelineRun.Status.PARTIAL if errors else PipelineRun.Status.SUCCESS
        )
        run.finished_at = timezone.now()
        run.records_in = len(ids)
        run.records_out = created
        run.records_failed = rejected_total
        run.error_message = (
            f"{errors} record(s) raised unexpected errors." if errors else ""
        )
        run.save()

        logger.info(
            "Transform finished: %d in, %d created, %d rejected %s",
            len(ids), created, rejected_total, dict(rejected),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{run.status}: {len(ids)} in, {created} created, "
                f"{rejected_total} rejected {dict(rejected)}"
            )
        )

    def transform_one(self, raw: RawArticle) -> str | None:
        """Process one raw article. Returns a rejection reason, or None if created."""
        payload = raw.payload
        title = strip_html(payload.get("title", ""))
        description = strip_html(payload.get("summary", ""))

        reason = validate(title, description, raw.url)
        content_hash = ""
        if reason is None:
            content_hash = hashlib.sha256(
                normalize_title(title).encode("utf-8")
            ).hexdigest()
            if Article.objects.filter(content_hash=content_hash).exists():
                reason = "duplicate_title"

        if reason is not None:
            raw.status = RawArticle.Status.REJECTED
            raw.rejection_reason = reason
            raw.save(update_fields=["status", "rejection_reason"])
            return reason

        Article.objects.create(
            raw=raw,
            source=raw.source,
            title=title[:500],
            url=raw.url,
            description=description,
            published_at=parse_published(payload, raw.fetched_at),
            content_hash=content_hash,
        )
        raw.status = RawArticle.Status.PROCESSED
        raw.save(update_fields=["status"])
        return None