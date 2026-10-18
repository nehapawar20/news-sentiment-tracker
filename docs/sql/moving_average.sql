-- Moving average of daily sentiment per topic, over the current row and the 6 before it.
-- Note: this counts rows, so if a topic has no articles on some days, the window
-- covers more than 7 calendar days.
SELECT date, topic, avg_sentiment,
       AVG(avg_sentiment) OVER (
           PARTITION BY topic
           ORDER BY date
           ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) AS moving_avg_7d
FROM news_dailytopicsentiment
ORDER BY topic, date;