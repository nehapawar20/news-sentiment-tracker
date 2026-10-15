import json

import pytest

from pipeline.enrichment.parsing import EnrichmentParseError, parse_enrichment

VALID = {
    "sentiment": "positive",
    "score": 0.6,
    "topic": "business",
    "entities": ["Acme"],
    "summary": "Acme grew strongly.",
}


def as_json(**changes):
    data = {**VALID, **changes}
    return json.dumps(data)


def test_valid_json_is_parsed():
    result = parse_enrichment(as_json())
    assert result.sentiment == "positive"
    assert result.score == 0.6
    assert result.topic == "business"
    assert result.entities == ["Acme"]


def test_json_in_code_fence_with_label():
    result = parse_enrichment(f"```json\n{as_json()}\n```")
    assert result.topic == "business"


def test_json_in_code_fence_without_label():
    result = parse_enrichment(f"```\n{as_json()}\n```")
    assert result.topic == "business"


def test_chatter_around_json_is_ignored():
    result = parse_enrichment(f"Here you go: {as_json()} Hope this helps!")
    assert result.sentiment == "positive"


def test_labels_are_case_insensitive():
    result = parse_enrichment(as_json(sentiment="Positive", topic=" BUSINESS "))
    assert result.sentiment == "positive"
    assert result.topic == "business"


def test_entities_default_to_empty_list():
    data = {key: value for key, value in VALID.items() if key != "entities"}
    assert parse_enrichment(json.dumps(data)).entities == []


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "I cannot help with that.",
        '{"sentiment": "positive"',
        as_json(score=1.7),
        as_json(score=-1.5),
        as_json(topic="cooking"),
        as_json(sentiment="happy"),
        as_json(summary="x" * 301),
        as_json(entities=[f"e{i}" for i in range(11)]),
        json.dumps({key: v for key, v in VALID.items() if key != "summary"}),
        json.dumps({key: v for key, v in VALID.items() if key != "score"}),
    ],
)
def test_bad_replies_are_rejected(reply):
    with pytest.raises(EnrichmentParseError):
        parse_enrichment(reply)