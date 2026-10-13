from datetime import UTC, datetime

import pytest

from pipeline.transformers.cleaning import normalize_title, parse_published, strip_html

FALLBACK = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("<p></p>", ""),
        ("Plain text", "Plain text"),
        ("<p>Hello <b>world</b></p>", "Hello world"),
        ("<div><p>One</p><p>Two</p></div>", "One Two"),
        ("Fish &amp; chips", "Fish & chips"),
        ("Caf&eacute;", "Café"),
        ("  lots\n\n of   space  ", "lots of space"),
        ("<script>alert(1)</script>Real text", "Real text"),
        ('<a href="https://x.com">link</a> after', "link after"),
    ],
)
def test_strip_html(raw, expected):
    assert strip_html(raw) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("", ""),
        ("!!!", ""),
        ("Breaking: Markets FALL!", "breaking markets fall"),
        ("  Hello,   World  ", "hello world"),
        ("Abramovich’s yachts", "abramovichs yachts"),
        ("Tech & AI: What's next?", "tech ai whats next"),
    ],
)
def test_normalize_title(title, expected):
    assert normalize_title(title) == expected


def test_normalize_title_matches_across_punctuation():
    assert normalize_title("Big News!") == normalize_title("big   news")


def test_parse_published_from_time_tuple():
    entry = {"published_parsed": (2026, 10, 12, 5, 0, 52, 0, 285, 0)}
    result = parse_published(entry, FALLBACK)
    assert result == datetime(2026, 10, 12, 5, 0, 52, tzinfo=UTC)


def test_parse_published_from_list():
    # JSON stores tuples as lists, so saved payloads look like this.
    entry = {"published_parsed": [2026, 10, 12, 5, 0, 52, 0, 285, 0]}
    assert parse_published(entry, FALLBACK) == datetime(
        2026, 10, 12, 5, 0, 52, tzinfo=UTC
    )


def test_parse_published_from_iso_string():
    entry = {"published": "2026-10-12T05:00:52+00:00"}
    assert parse_published(entry, FALLBACK) == datetime(
        2026, 10, 12, 5, 0, 52, tzinfo=UTC
    )


def test_parse_published_converts_offset_to_utc():
    entry = {"published": "2026-10-12T10:30:52+05:30"}
    assert parse_published(entry, FALLBACK) == datetime(
        2026, 10, 12, 5, 0, 52, tzinfo=UTC
    )


def test_parse_published_assumes_utc_for_naive_iso_string():
    entry = {"published": "2026-10-12T05:00:52"}
    result = parse_published(entry, FALLBACK)
    assert result.tzinfo is not None
    assert result == datetime(2026, 10, 12, 5, 0, 52, tzinfo=UTC)


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"published_parsed": None},
        {"published": None},
        {"published": "not a date"},
        {"published_parsed": "nonsense"},
        {"published_parsed": (2026, 13, 40, 0, 0, 0)},
    ],
)
def test_parse_published_falls_back_when_date_is_missing_or_bad(entry):
    assert parse_published(entry, FALLBACK) == FALLBACK