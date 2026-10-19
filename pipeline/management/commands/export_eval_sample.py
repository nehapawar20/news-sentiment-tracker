import random
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from news.models import Article, ArticleEnrichment
from pipeline.evaluation import write_sample


class Command(BaseCommand):
    help = "Export a random sample of enriched articles for hand labelling."

    def add_arguments(self, parser):
        parser.add_argument("--size", type=int, default=50)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--output", default="evaluation/eval_sample.csv")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite the file. Warning: this erases labels you already made.",
        )

    def handle(self, *args, **options):
        path = Path(options["output"])
        if path.exists() and not options["force"]:
            raise CommandError(
                f"{path} already exists. Use --force only if you want to start over."
            )

        ids = list(
            ArticleEnrichment.objects.order_by("article_id").values_list("article_id", flat=True)
        )
        if not ids:
            raise CommandError("No enriched articles yet. Run enrich_articles first.")

        size = min(options["size"], len(ids))
        chosen = random.Random(options["seed"]).sample(ids, size)
        articles = Article.objects.in_bulk(chosen)

        rows = []
        for article_id in chosen:
            article = articles[article_id]
            rows.append(
                {
                    "id": article.pk,
                    "title": " ".join(article.title.split()),
                    "description": " ".join(article.description.split())[:400],
                    "human_label": "",
                }
            )
        write_sample(path, rows)
        self.stdout.write(self.style.SUCCESS(f"Wrote {size} articles to {path}"))
