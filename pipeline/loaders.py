from news.models import RawArticle

from .utils import make_url_hash


def load_raw_articles(source, items: list[dict]) -> int:
    """Save fetched items as RawArticle rows. Returns how many were new."""
    objs = [
        RawArticle(
            source=source,
            url=item["url"],
            url_hash=make_url_hash(item["url"]),
            payload=item,
        )
        for item in items
    ]
    before = RawArticle.objects.count()
    RawArticle.objects.bulk_create(objs, batch_size=500, ignore_conflicts=True)
    return RawArticle.objects.count() - before
