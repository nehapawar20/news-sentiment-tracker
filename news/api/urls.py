from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleViewSet,
    HealthView,
    PipelineRunViewSet,
    TopicSummaryView,
    TrendView,
)

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("pipeline-runs", PipelineRunViewSet, basename="pipeline-run")

urlpatterns = [
    path("topics/", TopicSummaryView.as_view(), name="topics"),
    path("trends/", TrendView.as_view(), name="trends"),
    path("health/", HealthView.as_view(), name="health"),
    *router.urls,
]
