import logging
import time
from dataclasses import dataclass, field

from django.db import transaction

from news.models import Article, ArticleEnrichment

from .classifier import classify_article
from .llm_client import LLMUnavailableError
from .prompts import PROMPT_VERSION
from .vader import vader_score

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass
class EnrichStats:
    selected: int = 0
    enriched: int = 0
    failed: int = 0  # articles that failed during this run
    marked_failed: int = 0  # articles that reached the attempt limit
    input_tokens: int = 0
    output_tokens: int = 0
    aborted: bool = False  # True when the LLM itself was unreachable
    errors: list[str] = field(default_factory=list)


def pending_articles(limit: int):
    """Newest pending articles that still have attempts left."""
    return Article.objects.filter(
        enrichment_status=Article.EnrichmentStatus.PENDING,
        enrichment_attempts__lt=MAX_ATTEMPTS,
    ).order_by("-published_at", "-id")[:limit]


def _record_failure(article: Article, exc: Exception, stats: EnrichStats) -> None:
    article.enrichment_attempts += 1
    if article.enrichment_attempts >= MAX_ATTEMPTS:
        article.enrichment_status = Article.EnrichmentStatus.FAILED
        stats.marked_failed += 1
    article.save(update_fields=["enrichment_attempts", "enrichment_status"])
    stats.failed += 1
    stats.errors.append(f"article {article.pk}: {exc}")
    logger.warning(
        "Enrichment failed for article %s (attempt %d of %d): %s",
        article.pk,
        article.enrichment_attempts,
        MAX_ATTEMPTS,
        exc,
    )


def _save_result(article: Article, client, result, usage: dict) -> None:
    with transaction.atomic():
        ArticleEnrichment.objects.update_or_create(
            article=article,
            defaults={
                "sentiment_label": result.sentiment,
                "sentiment_score": result.score,
                "vader_score": vader_score(f"{article.title}. {article.description}"),
                "topic": result.topic,
                "entities": result.entities,
                "summary": result.summary,
                "model_name": getattr(client, "model", "unknown"),
                "prompt_version": PROMPT_VERSION,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            },
        )
        article.enrichment_status = Article.EnrichmentStatus.DONE
        article.save(update_fields=["enrichment_status"])


def enrich_pending(client, limit: int, sleep_seconds: float = 0.0) -> EnrichStats:
    """Enrich up to `limit` pending articles. Each article is isolated from the rest."""
    stats = EnrichStats()
    articles = list(pending_articles(limit))
    stats.selected = len(articles)

    for index, article in enumerate(articles):
        try:
            result, usage = classify_article(client, article.title, article.description)
        except LLMUnavailableError as exc:
            # Not the article's fault: stop the run and keep its attempts untouched.
            stats.aborted = True
            stats.errors.append(f"LLM unavailable: {exc}")
            logger.error("Stopping run, LLM unavailable: %s", exc)
            break
        except Exception as exc:  # a bad answer for one article must not stop the rest
            _record_failure(article, exc, stats)
            continue

        try:
            _save_result(article, client, result, usage)
        except Exception as exc:
            _record_failure(article, exc, stats)
            continue

        stats.enriched += 1
        stats.input_tokens += usage["input_tokens"]
        stats.output_tokens += usage["output_tokens"]

        if sleep_seconds and index < len(articles) - 1:
            time.sleep(sleep_seconds)

    return stats