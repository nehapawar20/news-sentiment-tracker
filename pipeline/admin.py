from django.contrib import admin

from .models import PipelineRun


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = (
        "stage",
        "status",
        "started_at",
        "finished_at",
        "records_in",
        "records_out",
        "records_failed",
    )
    list_filter = ("stage", "status")
    search_fields = ("error_message",)
