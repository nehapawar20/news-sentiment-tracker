import json

import pytest

from pipeline.enrichment.classifier import EnrichmentError, classify_article
from pipeline.enrichment.llm_client import LLMUnavailableError

GOOD = json.dumps(
    {
        "sentiment": "negative",
        "score": -0.5,
        "topic": "world",
        "entities": [],
        "summary": "Something bad happened.",
    }
)


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, user, json_mode=False, temperature=0.0):
        self.calls.append(
            {"user": user, "json_mode": json_mode, "temperature": temperature}
        )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, {"input_tokens": 10, "output_tokens": 5}


def test_returns_result_and_usage():
    fake = FakeLLM([GOOD])

    result, usage = classify_article(fake, "Title", "Description")

    assert result.sentiment == "negative"
    assert result.topic == "world"
    assert usage == {"input_tokens": 10, "output_tokens": 5}


def test_asks_for_json_mode():
    fake = FakeLLM([GOOD])

    classify_article(fake, "Title", "Description")

    assert fake.calls[0]["json_mode"] is True
    assert "<article>" in fake.calls[0]["user"]


def test_retries_once_after_a_bad_reply_with_higher_temperature():
    fake = FakeLLM(["not json at all", GOOD])

    result, usage = classify_article(fake, "Title", "Description")

    assert result.topic == "world"
    assert len(fake.calls) == 2
    assert fake.calls[0]["temperature"] == 0.0
    assert fake.calls[1]["temperature"] == 0.3
    assert usage == {"input_tokens": 20, "output_tokens": 10}


def test_gives_up_after_two_bad_replies():
    fake = FakeLLM(["bad", "still bad"])

    with pytest.raises(EnrichmentError):
        classify_article(fake, "Title", "Description")

    assert len(fake.calls) == 2


def test_unreachable_llm_is_not_retried():
    fake = FakeLLM([LLMUnavailableError("down")])

    with pytest.raises(LLMUnavailableError):
        classify_article(fake, "Title", "Description")

    assert len(fake.calls) == 1