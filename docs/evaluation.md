| Method | Accuracy | Articles answered |
|---|---|---|
| Majority baseline (always guess negative) | 56.0% | 50 |
| VADER | 60.0% | 50 |
| LLM v1 | 74.0% | 50 of 50 (sample contains only articles with a valid answer) |

In my first enrichment batch, 5 of 20 articles got no valid answer after two tries. All 5 failed because the model invented a topic outside the allowed list (environment, nature, animals, news).
