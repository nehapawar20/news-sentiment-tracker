import logging

from .parsing import EnrichmentParseError, parse_enrichment
from .prompts import SYSTEM_PROMPT, build_user_message
from .schemas import EnrichmentResult

logger = logging.getLogger(__name__)


class EnrichmentError(Exception):
    """The model never produced a valid answer."""


def classify_article(
    client, title: str, description: str, max_attempts: int = 2
) -> tuple[EnrichmentResult, dict]:
    """Ask the LLM to classify one article. Returns (result, total token usage)."""
    user_message = build_user_message(title, description)
    usage_total = {"input_tokens": 0, "output_tokens": 0}
    last_error = "no attempt made"

    for attempt in range(1, max_attempts + 1):
        # Same prompt at temperature 0 would give the same wrong answer,
        # so the retry uses a little randomness.
        temperature = 0.0 if attempt == 1 else 0.3
        text, usage = client.complete(
            SYSTEM_PROMPT, user_message, json_mode=True, temperature=temperature
        )
        usage_total["input_tokens"] += usage.get("input_tokens", 0)
        usage_total["output_tokens"] += usage.get("output_tokens", 0)

        try:
            return parse_enrichment(text), usage_total
        except EnrichmentParseError as exc:
            last_error = f"{exc} | reply started: {text[:120]!r}"
            logger.warning(
                "Attempt %d of %d: invalid LLM reply (%s)", attempt, max_attempts, exc
            )

    raise EnrichmentError(
        f"No valid answer after {max_attempts} attempts: {last_error}"
    )