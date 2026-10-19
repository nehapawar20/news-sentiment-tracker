import csv
from collections import Counter
from pathlib import Path

LABELS = ("positive", "neutral", "negative")
SAMPLE_COLUMNS = ["id", "title", "description", "human_label"]


def accuracy(pairs) -> float:
    """pairs is a list of (human_label, predicted_label)."""
    if not pairs:
        return 0.0
    return sum(1 for human, predicted in pairs if human == predicted) / len(pairs)


def majority_baseline(human_labels) -> float:
    """Accuracy of always guessing the most common human label."""
    if not human_labels:
        return 0.0
    most_common_count = Counter(human_labels).most_common(1)[0][1]
    return most_common_count / len(human_labels)


def confusion_matrix(pairs) -> dict:
    counts = Counter(pairs)
    return {
        human: {predicted: counts[(human, predicted)] for predicted in LABELS} for human in LABELS
    }


def confusion_table(matrix: dict) -> str:
    """A Markdown table: rows are your labels, columns are the model's guesses."""
    lines = [
        "| your label / model said | positive | neutral | negative |",
        "|---|---|---|---|",
    ]
    for human in LABELS:
        cells = " | ".join(str(matrix[human][predicted]) for predicted in LABELS)
        lines.append(f"| {human} | {cells} |")
    return "\n".join(lines)


def read_sample(path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_sample(path, rows) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
