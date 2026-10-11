from django.db import models

# Create your models here.


class Source(models.Model):
    """A place we collect news from (for now, an RSS feed)."""

    class SourceType(models.TextChoices):
        RSS = "rss", "RSS"
        API = "api", "API"

    name = models.CharField(max_length=100)
    source_type = models.CharField(
        max_length=10, choices=SourceType.choices, default=SourceType.RSS
    )
    feed_url = models.URLField(max_length=500, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RawArticle(models.Model):
    """The article exactly as fetched, before any cleaning."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        PROCESSED = "processed", "Processed"
        REJECTED = "rejected", "Rejected"

    source = models.ForeignKey(
        Source, on_delete=models.CASCADE, related_name="raw_articles"
    )
    url = models.URLField(max_length=1000)
    url_hash = models.CharField(max_length=64, unique=True, db_index=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.NEW, db_index=True
    )
    rejection_reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.url} [{self.status}]"


class Article(models.Model):
    """A cleaned article, ready for enrichment."""

    class EnrichmentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    raw = models.OneToOneField(
        RawArticle, on_delete=models.CASCADE, related_name="article"
    )
    source = models.ForeignKey(
        Source, on_delete=models.CASCADE, related_name="articles"
    )
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    published_at = models.DateTimeField(db_index=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    enrichment_status = models.CharField(
        max_length=10,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING,
        db_index=True,
    )
    enrichment_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title