# News Sentiment & Topic Tracker

An end-to-end data pipeline that collects news articles from RSS feeds, cleans and de-duplicates them, and uses an LLM to classify each article's sentiment and topic.

Results are stored in PostgreSQL, aggregated into daily trends, and served through a documented REST API and a simple dashboard. It helps analysts see how the tone of news coverage changes over time for topics like politics, business and technology.

Built with Python, Django, Django REST Framework and PostgreSQL.

## Quick start

Requires Python 3.11+ and PostgreSQL.

```bash
git clone git@github.com:nehapawar20/news-sentiment-tracker.git
cd news-sentiment-tracker

python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash); on macOS/Linux: source .venv/bin/activate
pip install -r requirements/dev.txt

cp .env.example .env                 # then edit .env with your own values
```

Create the database (in `psql`):

```sql
CREATE USER newsuser WITH PASSWORD 'change-me';
ALTER USER newsuser CREATEDB;
CREATE DATABASE newstracker OWNER newsuser;
```

Then:

```bash
python manage.py migrate
python manage.py seed_sources        # create the default RSS sources
python manage.py fetch_articles      # download raw articles
python manage.py transform_articles  # clean and de-duplicate them
python manage.py createsuperuser
python manage.py runserver           # browse data at /admin/
```

Run the tests:

```bash
pytest --cov=news --cov=pipeline
ruff check .
```

See `docs/` for requirements, architecture and data-quality rules.

## Dashboard

Run `python manage.py runserver` and open http://127.0.0.1:8000/ to see sentiment trends by topic, article counts per topic and the latest headlines. The API documentation is at http://127.0.0.1:8000/api/docs/.