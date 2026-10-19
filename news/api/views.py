from django.db import DatabaseError, connection
from django.db.models import Avg, Count, Max, Q
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from news.models import Article, ArticleEnrichment, DailyTopicSentiment
from pipeline.models import PipelineRun

from .filters import ArticleFilter, PipelineRunFilter
from .serializers import (
    ArticleSerializer,
    DateRangeQuerySerializer,
    HealthSerializer,
    PipelineRunSerializer,
    TopicSummarySerializer,
    TrendPointSerializer,
    TrendQuerySerializer,
)


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list and detail of articles, with their sentiment and topic."""

    # select_related joins source and enrichment into the same query,
    # so a page of 20 articles costs 2 queries, not 41.
    queryset = Article.objects.select_related("source", "enrichment")
    serializer_class = ArticleSerializer
    filterset_class = ArticleFilter
    search_fields = ["title", "description"]
    ordering_fields = ["published_at", "enrichment__sentiment_score"]
    ordering = ["-published_at", "-id"]


class PipelineRunViewSet(viewsets.ReadOnlyModelViewSet):
    """History of pipeline runs, newest first."""

    queryset = PipelineRun.objects.all()
    serializer_class = PipelineRunSerializer
    filterset_class = PipelineRunFilter
    ordering_fields = ["started_at", "finished_at"]
    ordering = ["-started_at", "-id"]


class TopicSummaryView(APIView):
    """Article counts and average sentiment per topic, optionally within a date range."""

    @extend_schema(
        parameters=[DateRangeQuerySerializer],
        responses=TopicSummarySerializer(many=True),
    )
    def get(self, request):
        params = DateRangeQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        start = params.validated_data.get("from")
        end = params.validated_data.get("to")

        enrichments = ArticleEnrichment.objects.all()
        if start:
            enrichments = enrichments.filter(article__published_at__date__gte=start)
        if end:
            enrichments = enrichments.filter(article__published_at__date__lte=end)

        rows = (
            enrichments.values("topic")
            .annotate(
                article_count=Count("id"),
                avg_sentiment=Avg("sentiment_score"),
                positive_count=Count("id", filter=Q(sentiment_label="positive")),
                neutral_count=Count("id", filter=Q(sentiment_label="neutral")),
                negative_count=Count("id", filter=Q(sentiment_label="negative")),
            )
            .order_by("-article_count", "topic")
        )
        data = [{**row, "avg_sentiment": round(row["avg_sentiment"], 4)} for row in rows]
        return Response(TopicSummarySerializer(data, many=True).data)


class TrendView(APIView):
    """Daily sentiment series from the pre-computed DailyTopicSentiment table."""

    @extend_schema(
        parameters=[TrendQuerySerializer],
        responses=TrendPointSerializer(many=True),
    )
    def get(self, request):
        params = TrendQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        topic = params.validated_data.get("topic")
        start = params.validated_data.get("from")
        end = params.validated_data.get("to")

        points = DailyTopicSentiment.objects.all()
        if topic:
            points = points.filter(topic=topic)
        if start:
            points = points.filter(date__gte=start)
        if end:
            points = points.filter(date__lte=end)

        points = points.order_by("date", "topic")
        return Response(TrendPointSerializer(points, many=True).data)


class HealthView(APIView):
    """Is the app alive, can it reach its database, and when did the pipeline last succeed?"""

    throttle_classes = []  # monitoring tools may call this often

    @extend_schema(responses=HealthSerializer)
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database_ok = True
        except DatabaseError:
            database_ok = False

        last_by_stage = {}
        if database_ok:
            rows = (
                PipelineRun.objects.filter(
                    status=PipelineRun.Status.SUCCESS, finished_at__isnull=False
                )
                .values("stage")
                .annotate(last=Max("finished_at"))
            )
            last_by_stage = {row["stage"]: row["last"] for row in rows}

        payload = {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "error",
            "last_successful_run": max(last_by_stage.values(), default=None),
            "last_successful_run_by_stage": last_by_stage,
        }
        return Response(payload, status=200 if database_ok else 503)
