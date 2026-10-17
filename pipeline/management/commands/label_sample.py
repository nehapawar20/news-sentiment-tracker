from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from pipeline.evaluation import read_sample, write_sample

KEYS = {"1": "positive", "2": "neutral", "3": "negative"}

GUIDELINES = """
How to label (decide this once, then be consistent):
  positive = mainly good news: wins, growth, rescues, discoveries, agreements
  negative = mainly bad news: deaths, crime, disasters, losses, conflict
  neutral  = factual, mixed, or no clear good or bad tone: announcements, schedules
Judge the overall tone of the story, not how you feel about the topic.
"""


class Command(BaseCommand):
    help = "Label the evaluation sample by hand, one article at a time."

    def add_arguments(self, parser):
        parser.add_argument("--file", default="evaluation/eval_sample.csv")

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"{path} not found. Run export_eval_sample first.")

        rows = read_sample(path)
        total = len(rows)
        self.stdout.write(GUIDELINES)

        for number, row in enumerate(rows, start=1):
            if row["human_label"]:
                continue
            self.stdout.write(f"\n[{number}/{total}] {row['title']}")
            if row["description"]:
                self.stdout.write(f"    {row['description']}")
            while True:
                try:
                    answer = input("1=positive 2=neutral 3=negative s=skip q=quit > ")
                except EOFError:
                    self.stdout.write("Input closed. Progress saved.")
                    return
                answer = answer.strip().lower()
                if answer in KEYS:
                    row["human_label"] = KEYS[answer]
                    write_sample(path, rows)
                    break
                if answer == "s":
                    break
                if answer == "q":
                    self.stdout.write("Progress saved. Run the command again to continue.")
                    return
                self.stdout.write("Please type 1, 2, 3, s or q.")

        self.stdout.write(self.style.SUCCESS("Every row has been visited."))