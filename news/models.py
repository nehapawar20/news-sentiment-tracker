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

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="raw_articles")
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

    raw = models.OneToOneField(RawArticle, on_delete=models.CASCADE, related_name="article")
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="articles")
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


class ArticleEnrichment(models.Model):
    """Sentiment, topic and summary produced for one article."""

    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    class Topic(models.TextChoices):
        POLITICS = "politics", "Politics"
        BUSINESS = "business", "Business"
        TECHNOLOGY = "technology", "Technology"
        SPORTS = "sports", "Sports"
        HEALTH = "health", "Health"
        SCIENCE = "science", "Science"
        ENTERTAINMENT = "entertainment", "Entertainment"
        WORLD = "world", "World"
        OTHER = "other", "Other"

    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name="enrichment")
    sentiment_label = models.CharField(max_length=10, choices=Sentiment.choices, db_index=True)
    sentiment_score = models.FloatField()  # -1.0 to 1.0
    vader_score = models.FloatField(null=True, blank=True)
    topic = models.CharField(max_length=20, choices=Topic.choices, db_index=True)
    entities = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.article_id}: {self.sentiment_label} / {self.topic}"


class DailyTopicSentiment(models.Model):
    """Average sentiment for one topic on one day."""

    date = models.DateField()
    topic = models.CharField(max_length=20)
    avg_sentiment = models.FloatField()
    article_count = models.IntegerField(default=0)
    positive_count = models.IntegerField(default=0)
    neutral_count = models.IntegerField(default=0)
    negative_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "topic"], name="unique_date_topic")]
        ordering = ["-date", "topic"]

    def __str__(self):
        return f"{self.date} {self.topic}: {self.avg_sentiment:.2f}"
