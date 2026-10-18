from rest_framework import serializers

from news.models import Article, ArticleEnrichment


class ArticleEnrichmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleEnrichment
        fields = [
            "sentiment_label",
            "sentiment_score",
            "vader_score",
            "topic",
            "entities",
            "summary",
            "model_name",
            "prompt_version",
            "processed_at",
        ]
        read_only_fields = fields


class ArticleSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source="source.name", read_only=True)
    # allow_null makes un-enriched articles show "enrichment": null
    # instead of leaving the key out.
    enrichment = ArticleEnrichmentSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "url",
            "description",
            "published_at",
            "source",
            "enrichment_status",
            "enrichment",
        ]
        read_only_fields = fields