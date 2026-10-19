import hashlib

import factory
from django.utils import timezone

from news.models import Article, RawArticle, Source


class SourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Source

    name = factory.Sequence(lambda n: f"Source {n}")
    source_type = Source.SourceType.RSS
    feed_url = factory.Sequence(lambda n: f"https://example.com/feed{n}.xml")
    is_active = True


class RawArticleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RawArticle

    source = factory.SubFactory(SourceFactory)
    url = factory.Sequence(lambda n: f"https://example.com/story/{n}")
    url_hash = factory.LazyAttribute(lambda obj: hashlib.sha256(obj.url.encode()).hexdigest())
    payload = factory.LazyFunction(lambda: {"title": "Test headline"})
    status = RawArticle.Status.NEW


class ArticleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Article

    raw = factory.SubFactory(RawArticleFactory)
    source = factory.SelfAttribute("raw.source")
    title = factory.Sequence(lambda n: f"Headline {n}")
    url = factory.SelfAttribute("raw.url")
    description = "A short description."
    published_at = factory.LazyFunction(timezone.now)
    content_hash = factory.LazyAttribute(lambda obj: hashlib.sha256(obj.title.encode()).hexdigest())
