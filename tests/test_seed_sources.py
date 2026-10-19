from io import StringIO

import pytest
from django.core.management import call_command

from news.models import Source
from pipeline.management.commands.seed_sources import SOURCES

pytestmark = pytest.mark.django_db


def run_seed():
    out = StringIO()
    call_command("seed_sources", stdout=out)
    return out.getvalue()


def test_default_sources_have_unique_https_urls():
    urls = [url for _, url in SOURCES]

    assert len(urls) == len(set(urls))
    assert all(url.startswith("https://") for url in urls)


def test_seed_creates_the_default_sources():
    output = run_seed()

    assert Source.objects.count() == len(SOURCES)
    assert f"{len(SOURCES)} created" in output


def test_seed_twice_creates_no_duplicates_and_keeps_edits():
    run_seed()
    source = Source.objects.first()
    source.is_active = False
    source.save()

    output = run_seed()

    source.refresh_from_db()
    assert Source.objects.count() == len(SOURCES)
    assert "0 created" in output
    assert source.is_active is False  # re-seeding must not undo manual changes
