import django_filters

from news.models import Article, ArticleEnrichment
from pipeline.models import PipelineRun


class ArticleFilter(django_filters.FilterSet):
    topic = django_filters.ChoiceFilter(
        field_name="enrichment__topic", choices=ArticleEnrichment.Topic.choices
    )
    sentiment_label = django_filters.ChoiceFilter(
        field_name="enrichment__sentiment_label",
        choices=ArticleEnrichment.Sentiment.choices,
    )
    source = django_filters.CharFilter(
        field_name="source__name",
        lookup_expr="icontains",
        help_text="Part of the source name, for example 'business'.",
    )
    published_after = django_filters.DateFilter(
        field_name="published_at",
        lookup_expr="date__gte",
        help_text="UTC date, YYYY-MM-DD, inclusive.",
    )
    published_before = django_filters.DateFilter(
        field_name="published_at",
        lookup_expr="date__lte",
        help_text="UTC date, YYYY-MM-DD, inclusive.",
    )

    class Meta:
        model = Article
        fields = []
        
class PipelineRunFilter(django_filters.FilterSet):
    class Meta:
        model = PipelineRun
        fields = ["stage", "status"]