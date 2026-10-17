-- Recompute the daily aggregation in plain SQL and compare it with the stored table.
-- No rows returned means the two agree.
WITH live AS (
    SELECT (a.published_at AT TIME ZONE 'UTC')::date AS day,
           e.topic,
           AVG(e.sentiment_score) AS avg_sentiment,
           COUNT(*) AS article_count,
           COUNT(*) FILTER (WHERE e.sentiment_label = 'positive') AS positive_count,
           COUNT(*) FILTER (WHERE e.sentiment_label = 'neutral')  AS neutral_count,
           COUNT(*) FILTER (WHERE e.sentiment_label = 'negative') AS negative_count
    FROM news_articleenrichment e
    JOIN news_article a ON a.id = e.article_id
    GROUP BY 1, 2
)
SELECT l.day, l.topic, l.article_count AS sql_count,
       d.article_count AS stored_count, l.avg_sentiment AS sql_avg,
       d.avg_sentiment AS stored_avg
FROM live l
FULL JOIN news_dailytopicsentiment d
       ON d.date = l.day AND d.topic = l.topic
WHERE d.id IS NULL
   OR l.day IS NULL
   OR d.article_count <> l.article_count
   OR d.positive_count <> l.positive_count
   OR d.neutral_count <> l.neutral_count
   OR d.negative_count <> l.negative_count
   OR ABS(d.avg_sentiment - l.avg_sentiment) > 0.000001;