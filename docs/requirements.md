# Requirements

## Problem statement
News coverage changes daily, and it is hard to see how the tone of coverage differs across topics over time. This project collects news articles automatically, classifies each one by sentiment and topic, and exposes the results through an API and dashboard so analysts can spot trends quickly.

## User stories
1. As an analyst, I can filter articles by topic and sentiment.
2. As an analyst, I can see how average sentiment for a topic changes day by day.
3. As a reader, I can click through from any article to its original source.
4. As a developer, I can re-run the pipeline without creating duplicate articles.
5. As an operator, I can see which pipeline runs failed and why.
6. As a developer, I can browse interactive API documentation at `/api/docs/`.
7. As an operator, I can add or disable a news source without changing code.
8. As a maintainer, I can run the test suite and trust that external services are mocked.

## MVP scope
- 6 or more RSS sources, fetched on a schedule
- Raw storage, cleaning and de-duplication
- VADER baseline plus LLM enrichment (sentiment, topic, entities, summary)
- Daily aggregation per topic
- Read-only REST API with filters, pagination and OpenAPI docs
- Dashboard with 3 charts or tables
- Tests, Docker, CI and README

## Non-goals
- No user accounts or login
- No republishing of full article text (title, link, short description only)
- No real-time streaming; the pipeline runs in scheduled batches
- No cloud deployment in the MVP