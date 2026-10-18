from rest_framework import viewsets

from news.models import Article

from .filters import ArticleFilter
from .serializers import ArticleSerializer


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