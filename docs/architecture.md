# Architecture

## Pipeline

```mermaid
flowchart LR
  A[RSS feeds / News API] --> B[Extract]
  B --> C[(RawArticle: raw storage)]
  C --> D[Transform and clean]
  D --> E[(Article: cleaned)]
  E --> F[Enrich: VADER + LLM]
  F --> G[(ArticleEnrichment)]
  G --> H[Aggregate daily]
  H --> I[(DailyTopicSentiment)]
  E --> J[REST API - DRF]
  G --> J
  I --> J
  J --> K[Dashboard - Chart.js]
  B -.-> L[(PipelineRun logs)]
  D -.-> L
  F -.-> L
  H -.-> L
```

## Stages

**Extract.** Input: active sources (RSS feed URLs). Output: one `RawArticle` row per feed entry, stored exactly as fetched. Failure behaviour: a failing feed is logged and skipped so other feeds still run. Duplicates are ignored using a unique URL hash.

**Transform.** Input: `RawArticle` rows with status `new`. Output: cleaned `Article` rows (HTML stripped, UTC dates, content hash). Failure behaviour: invalid records are marked `rejected` with a reason, never deleted.

**Enrich.** Input: `Article` rows with enrichment status `pending`. Output: an `ArticleEnrichment` row with VADER score, LLM sentiment, topic, entities and summary. Failure behaviour: invalid LLM output is retried a limited number of times, then the article is marked `failed`. A daily cap limits cost.

**Aggregate.** Input: enriched articles. Output: one `DailyTopicSentiment` row per date and topic. Failure behaviour: re-running overwrites the same rows, so the result is the same each time.

**Serve.** The REST API reads from the tables above and the dashboard calls the API. Nothing is written through the API.

**Monitor.** Every stage writes a `PipelineRun` record with status, counts and any error message.

## Data model

```mermaid
erDiagram
  Source ||--o{ RawArticle : has
  Source ||--o{ Article : has
  RawArticle ||--o| Article : becomes
  Article ||--o| ArticleEnrichment : has

  Source {
    int id
    string name
    string source_type
    string feed_url
    bool is_active
  }
  RawArticle {
    string url
    string url_hash
    json payload
    string status
    string rejection_reason
  }
  Article {
    string title
    string url
    text description
    datetime published_at
    string content_hash
    string enrichment_status
  }
  ArticleEnrichment {
    string sentiment_label
    float sentiment_score
    float vader_score
    string topic
    json entities
    text summary
  }
  DailyTopicSentiment {
    date date
    string topic
    float avg_sentiment
    int article_count
  }
  PipelineRun {
    string stage
    string status
    int records_in
    int records_out
    int records_failed
  }
```