import pytest

from pipeline.enrichment.vader import vader_label, vader_score


def test_clearly_positive_headline():
    score = vader_score("Heroes celebrate great victory")
    assert score > 0.05
    assert vader_label(score) == "positive"


def test_clearly_negative_headline():
    score = vader_score("Deadly attack kills dozens, leaving city in terror")
    assert score < -0.05
    assert vader_label(score) == "negative"


def test_neutral_headline():
    score = vader_score("The meeting is scheduled for Tuesday")
    assert vader_label(score) == "neutral"


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_text_is_neutral(text):
    assert vader_score(text) == 0.0
    assert vader_label(vader_score(text)) == "neutral"


def test_negation_flips_the_score():
    assert vader_score("This is not good") < 0 < vader_score("This is good")


def test_score_stays_within_range():
    score = vader_score("AMAZING!!! Absolutely wonderful, fantastic, perfect!!!")
    assert -1.0 <= score <= 1.0


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1.0, "positive"),
        (0.05, "positive"),
        (0.049, "neutral"),
        (0.0, "neutral"),
        (-0.049, "neutral"),
        (-0.05, "negative"),
        (-1.0, "negative"),
    ],
)
def test_label_thresholds(score, expected):
    assert vader_label(score) == expected
