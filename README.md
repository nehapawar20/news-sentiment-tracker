# News Sentiment & Topic Tracker

An end-to-end data pipeline that collects news articles from RSS feeds, cleans and de-duplicates them, and uses an LLM to classify each article's sentiment and topic.

Results are stored in PostgreSQL, aggregated into daily trends, and served through a documented REST API and a simple dashboard. It helps analysts see how the tone of news coverage changes over time for topics like politics, business and technology.

Built with Python, Django, Django REST Framework and PostgreSQL.