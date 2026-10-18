from datetime import date

from django.db import transaction
from django.db.models import Avg, Count, Q

from news.models import ArticleEnrichment, DailyTopicSentiment


def aggregate_day(day: date) -> dict:
    """Recompute the DailyTopicSentiment rows for one day (UTC).

    Safe to run any number of times: rows are updated in place, and rows for topics
    that no longer have articles on that day are removed.
    """
    rows = list(
        ArticleEnrichment.objects.filter(article__published_at__date=day)
        .values("topic")
        .annotate(
            avg_sentiment=Avg("sentiment_score"),
            article_count=Count("id"),
            positive_count=Count("id", filter=Q(sentiment_label="positive")),
            neutral_count=Count("id", filter=Q(sentiment_label="neutral")),
            negative_count=Count("id", filter=Q(sentiment_label="negative")),
        )
        .order_by("topic")
    )

    created = updated = 0
    with transaction.atomic():
        for row in rows:
            _, was_created = DailyTopicSentiment.objects.update_or_create(
                date=day,
                topic=row["topic"],
                defaults={
                    "avg_sentiment": row["avg_sentiment"],
                    "article_count": row["article_count"],
                    "positive_count": row["positive_count"],
                    "neutral_count": row["neutral_count"],
                    "negative_count": row["negative_count"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        deleted, _ = (
            DailyTopicSentiment.objects.filter(date=day)
            .exclude(topic__in=[row["topic"] for row in rows])
            .delete()
        )

    return {
        "articles": sum(row["article_count"] for row in rows),
        "rows": len(rows),
        "created": created,
        "updated": updated,
        "deleted": deleted,
    }