import re

from pydantic import ValidationError

from .schemas import EnrichmentResult


class EnrichmentParseError(ValueError):
    """The model's reply was not a valid enrichment result."""


def extract_json(text: str) -> str:
    """Remove Markdown code fences and any chatter around the JSON object."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise EnrichmentParseError("no JSON object found in the reply")
    return cleaned[start : end + 1]


def parse_enrichment(text: str) -> EnrichmentResult:
    candidate = extract_json(text)
    try:
        return EnrichmentResult.model_validate_json(candidate)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()[:3]
        )
        raise EnrichmentParseError(f"reply failed validation: {problems}") from exc