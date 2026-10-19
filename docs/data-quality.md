# Data quality

The transform stage checks every raw record before it becomes an `Article`.
Records that fail a rule are never deleted. They are marked `rejected` with a reason, so the decision can always be audited.

## Rules

| Order | Rule | Rejection reason |
|---|---|---|
| 1 | The title must contain at least one real word after cleaning | `empty_title` |
| 2 | The URL must start with `http` | `invalid_url` |
| 3 | Title and description together must be at least 20 characters | `too_short` |
| 4 | No existing article may have the same normalised title | `duplicate_title` |
| - | Any unexpected error while processing a record | `transform_error` |

## Cleaning

- HTML tags and entities are removed from title and description (`strip_html`).
- Publication dates are converted to timezone-aware UTC. If the date is missing or invalid, the fetch time is used.
- Tracking parameters (`utm_*`, `at_*`, `fbclid`, ...) are removed from URLs before hashing, so the same article is not stored twice.

## Results from a real run (2026-10-13)

| Outcome | Count | Share |
|---|---|---|
| Processed into articles | 224 | 94.4% |
| Rejected: duplicate_title | 13 | 5.5% |
| **Total raw records** | **237** | 100% |

Most rejections are duplicates: the same BBC story often appears in more than one feed (for example Top Stories and Business).

## Re-running

The transform stage only reads records with status `new`, so running it again does nothing until new raw records arrive.
