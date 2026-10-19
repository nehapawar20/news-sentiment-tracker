#!/usr/bin/env bash
# Runs everything the project checks before a commit: lint, format, tests.
set -e
ruff check .
ruff format --check .
pytest --cov
echo "All checks passed."
