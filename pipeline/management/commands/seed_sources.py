from django.core.management.base import BaseCommand

from news.models import Source

SOURCES = [
    ("BBC News - Top Stories", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("BBC News - World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC News - Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC News - Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("BBC News - Health", "https://feeds.bbci.co.uk/news/health/rss.xml"),
    (
        "BBC News - Science & Environment",
        "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    ),
]


class Command(BaseCommand):
    help = "Create the default news sources (safe to run more than once)."

    def handle(self, *args, **options):
        created_count = 0
        for name, url in SOURCES:
            _, created = Source.objects.get_or_create(
                feed_url=url,
                defaults={"name": name, "source_type": Source.SourceType.RSS},
            )
            if created:
                created_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created_count} created, "
                f"{len(SOURCES) - created_count} already existed."
            )
        )