
# Register your models here.
from django.contrib import admin

from .models import (
    Article,
    ArticleEnrichment,
    DailyTopicSentiment,
    RawArticle,
    Source,
)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "feed_url", "is_active")
    list_filter = ("source_type", "is_active")
    search_fields = ("name", "feed_url")


@admin.register(RawArticle)
class RawArticleAdmin(admin.ModelAdmin):
    list_display = ("url", "source", "status", "fetched_at")
    list_filter = ("status", "source")
    search_fields = ("url",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "enrichment_status")
    list_filter = ("enrichment_status", "source")
    search_fields = ("title", "description")


@admin.register(ArticleEnrichment)
class ArticleEnrichmentAdmin(admin.ModelAdmin):
    list_display = ("article", "sentiment_label", "sentiment_score", "topic")
    list_filter = ("sentiment_label", "topic")
    search_fields = ("article__title", "summary")


@admin.register(DailyTopicSentiment)
class DailyTopicSentimentAdmin(admin.ModelAdmin):
    list_display = ("date", "topic", "avg_sentiment", "article_count")
    list_filter = ("topic",)