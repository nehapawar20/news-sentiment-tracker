from django.db import models


class PipelineRun(models.Model):
    """One run of one pipeline stage, for monitoring."""

    class Stage(models.TextChoices):
        EXTRACT = "extract", "Extract"
        TRANSFORM = "transform", "Transform"
        ENRICH = "enrich", "Enrich"
        AGGREGATE = "aggregate", "Aggregate"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    stage = models.CharField(max_length=20, choices=Stage.choices, db_index=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.RUNNING, db_index=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_in = models.IntegerField(default=0)
    records_out = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.stage} {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"