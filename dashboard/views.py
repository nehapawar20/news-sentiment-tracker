from django.views.generic import TemplateView

from news.models import ArticleEnrichment


class DashboardView(TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # One source of truth for the topic list: the model.
        context["topics"] = ArticleEnrichment.Topic.choices
        return context