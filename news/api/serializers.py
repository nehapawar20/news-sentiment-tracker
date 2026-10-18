from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from news.models import Article, ArticleEnrichment, DailyTopicSentiment
from pipeline.models import PipelineRun


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

class DateRangeQuerySerializer(serializers.Serializer):
    """Checks the ?from= and ?to= URL parameters (YYYY-MM-DD, inclusive)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'from' is a Python keyword, so these fields cannot be declared as attributes.
        self.fields["from"] = serializers.DateField(required=False)
        self.fields["to"] = serializers.DateField(required=False)

    def validate(self, attrs):
        start, end = attrs.get("from"), attrs.get("to")
        if start and end and start > end:
            raise serializers.ValidationError("'from' must not be later than 'to'.")
        return attrs


class TrendQuerySerializer(DateRangeQuerySerializer):
    topic = serializers.ChoiceField(
        choices=ArticleEnrichment.Topic.choices, required=False
    )


class TopicSummarySerializer(serializers.Serializer):
    topic = serializers.CharField()
    article_count = serializers.IntegerField()
    avg_sentiment = serializers.FloatField()
    positive_count = serializers.IntegerField()
    neutral_count = serializers.IntegerField()
    negative_count = serializers.IntegerField()


class TrendPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyTopicSentiment
        fields = [
            "date",
            "topic",
            "avg_sentiment",
            "article_count",
            "positive_count",
            "neutral_count",
            "negative_count",
        ]
        read_only_fields = fields


class PipelineRunSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = PipelineRun
        fields = [
            "id",
            "stage",
            "status",
            "started_at",
            "finished_at",
            "duration_seconds",
            "records_in",
            "records_out",
            "records_failed",
            "error_message",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_duration_seconds(self, obj):
        if obj.finished_at is None:
            return None
        return (obj.finished_at - obj.started_at).total_seconds()


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()
    last_successful_run = serializers.DateTimeField(allow_null=True)
    last_successful_run_by_stage = serializers.DictField(
        child=serializers.DateTimeField()
    )