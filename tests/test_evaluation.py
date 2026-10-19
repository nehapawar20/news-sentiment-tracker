from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.models import ArticleEnrichment
from pipeline.evaluation import (
    SAMPLE_COLUMNS,
    accuracy,
    confusion_matrix,
    confusion_table,
    majority_baseline,
    read_sample,
    write_sample,
)
from tests.factories import ArticleFactory


def test_accuracy():
    pairs = [("positive", "positive"), ("neutral", "negative")]
    assert accuracy(pairs) == 0.5
    assert accuracy([]) == 0.0


def test_majority_baseline():
    assert majority_baseline(["positive", "positive", "neutral"]) == pytest.approx(2 / 3)
    assert majority_baseline([]) == 0.0


def test_confusion_matrix_counts():
    pairs = [
        ("positive", "positive"),
        ("positive", "neutral"),
        ("negative", "negative"),
        ("negative", "negative"),
    ]
    matrix = confusion_matrix(pairs)
    assert matrix["positive"]["positive"] == 1
    assert matrix["positive"]["neutral"] == 1
    assert matrix["negative"]["negative"] == 2
    assert matrix["neutral"]["neutral"] == 0


def test_confusion_table_is_markdown():
    table = confusion_table(confusion_matrix([("positive", "positive")]))
    assert table.startswith("| your label / model said |")
    assert "| positive | 1 | 0 | 0 |" in table


def test_sample_csv_round_trip_keeps_commas_and_quotes(tmp_path):
    path = tmp_path / "sample.csv"
    rows = [
        {
            "id": "1",
            "title": 'Hello, "world"',
            "description": "a, b, c",
            "human_label": "",
        }
    ]

    write_sample(path, rows)

    assert read_sample(path) == rows


@pytest.mark.django_db
class TestExportCommand:
    def make_enriched(self):
        article = ArticleFactory()
        ArticleEnrichment.objects.create(
            article=article,
            sentiment_label="positive",
            sentiment_score=0.5,
            topic="world",
        )
        return article

    def export(self, path, **options):
        call_command("export_eval_sample", output=str(path), stdout=StringIO(), **options)

    def test_export_is_blind_and_only_includes_enriched_articles(self, tmp_path):
        for _ in range(3):
            self.make_enriched()
        ArticleFactory()  # never enriched, so it must not appear
        path = tmp_path / "sample.csv"

        self.export(path, size=10)

        rows = read_sample(path)
        assert len(rows) == 3
        assert list(rows[0].keys()) == SAMPLE_COLUMNS
        assert all(row["human_label"] == "" for row in rows)

    def test_size_limits_the_sample(self, tmp_path):
        for _ in range(4):
            self.make_enriched()
        path = tmp_path / "sample.csv"

        self.export(path, size=2)

        assert len(read_sample(path)) == 2

    def test_same_seed_gives_same_sample(self, tmp_path):
        for _ in range(6):
            self.make_enriched()

        self.export(tmp_path / "a.csv", size=3, seed=7)
        self.export(tmp_path / "b.csv", size=3, seed=7)

        ids_a = [row["id"] for row in read_sample(tmp_path / "a.csv")]
        ids_b = [row["id"] for row in read_sample(tmp_path / "b.csv")]
        assert ids_a == ids_b

    def test_existing_file_is_not_overwritten_without_force(self, tmp_path):
        self.make_enriched()
        path = tmp_path / "sample.csv"
        self.export(path, size=1)

        with pytest.raises(CommandError):
            self.export(path, size=1)

        self.export(path, size=1, force=True)

    def test_no_enriched_articles_is_an_error(self, tmp_path):
        with pytest.raises(CommandError):
            self.export(tmp_path / "sample.csv")
