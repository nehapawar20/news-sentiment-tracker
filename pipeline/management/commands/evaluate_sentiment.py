from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from news.models import Article, ArticleEnrichment
from pipeline.enrichment.classifier import EnrichmentError, classify_article
from pipeline.enrichment.llm_client import LLMClient, LLMUnavailableError
from pipeline.enrichment.prompts import PROMPT_VERSION
from pipeline.enrichment.vader import vader_label, vader_score
from pipeline.evaluation import (
    LABELS,
    accuracy,
    confusion_matrix,
    confusion_table,
    majority_baseline,
    read_sample,
)

MAX_EXAMPLES = 8


class Command(BaseCommand):
    help = "Compare VADER and the LLM with your hand-made labels."

    def add_arguments(self, parser):
        parser.add_argument("--file", default="evaluation/eval_sample.csv")
        parser.add_argument(
            "--rerun",
            action="store_true",
            help="Ask the LLM again with the CURRENT prompt instead of using saved answers.",
        )

    def build_client(self):
        return LLMClient()

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"{path} not found.")

        rows = [r for r in read_sample(path) if r["human_label"] in LABELS]
        if len(rows) < 10:
            raise CommandError(
                f"Only {len(rows)} rows are labelled. Label at least 10 "
                "(ideally 50) with: python manage.py label_sample"
            )

        ids = [int(r["id"]) for r in rows]
        articles = Article.objects.in_bulk(ids)
        saved = {e.article_id: e for e in ArticleEnrichment.objects.filter(article_id__in=ids)}
        rerun = options["rerun"]
        client = self.build_client() if rerun else None

        humans, vader_pairs, llm_pairs = [], [], []
        vader_misses, llm_misses = [], []
        parse_failures = 0
        versions = Counter()

        for row in rows:
            article = articles.get(int(row["id"]))
            if article is None:
                continue
            human = row["human_label"]
            humans.append(human)

            vader = vader_label(vader_score(f"{article.title}. {article.description}"))
            vader_pairs.append((human, vader))
            if vader != human:
                vader_misses.append((human, vader, article.title))

            llm = None
            if rerun:
                try:
                    result, _usage = classify_article(client, article.title, article.description)
                    llm = result.sentiment
                    versions[PROMPT_VERSION] += 1
                except EnrichmentError:
                    parse_failures += 1
                except LLMUnavailableError as exc:
                    raise CommandError(f"The LLM is not reachable: {exc}") from exc
            elif article.pk in saved:
                llm = saved[article.pk].sentiment_label
                versions[saved[article.pk].prompt_version or "unknown"] += 1
            else:
                parse_failures += 1

            if llm is not None:
                llm_pairs.append((human, llm))
                if llm != human:
                    llm_misses.append((human, llm, article.title))

        total = len(humans)
        source = "re-run with the current prompt" if rerun else "answers saved in the database"
        out = self.stdout.write
        out(f"Evaluated {total} labelled articles. LLM answers: {source}.")
        out(f"Prompt version(s): {dict(versions)}")
        out(
            f"Majority baseline (always guess the most common label): "
            f"{majority_baseline(humans):.1%}\n"
        )

        out(f"## VADER: accuracy {accuracy(vader_pairs):.1%} ({total} articles)")
        out(confusion_table(confusion_matrix(vader_pairs)))
        self.show_misses("VADER", vader_misses)

        out(
            f"\n## LLM: accuracy {accuracy(llm_pairs):.1%} "
            f"({len(llm_pairs)} answered, {parse_failures} without a valid answer)"
        )
        out(confusion_table(confusion_matrix(llm_pairs)))
        self.show_misses("LLM", llm_misses)

    def show_misses(self, name, misses):
        if not misses:
            return
        self.stdout.write(f"\n{name} got these wrong (up to {MAX_EXAMPLES}):")
        for human, predicted, title in misses[:MAX_EXAMPLES]:
            self.stdout.write(f"  you={human:8} {name}={predicted:8} {title[:70]}")
