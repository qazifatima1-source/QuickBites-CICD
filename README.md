# Quick Bites – Simple Food Ordering App

A small **monolith**: Flask (Python) serves the pages and the logic, SQLite stores users, menu and orders.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # open http://localhost:5000
```

## Run tests
```bash
pytest
```

## Run with Docker
```bash
docker build -t quick-bites .
docker run -p 5000:5000 -e SECRET_KEY=change-me -v quickbites-data:/data quick-bites
```

## Project layout
| Path | Purpose |
|------|---------|
| `app.py` | All backend code: DB, login, menu, orders, health check |
| `templates/` | HTML pages (one file per page, `base.html` is the shared layout) |
| `static/style.css` | Colours and layout |
| `tests/test_app.py` | Automated tests (the CI step) |
| `Dockerfile` | Packages the app for AWS or any platform |
| `requirements.txt` | Python dependencies |

## How to change things
- **Menu items:** edit `DEFAULT_MENU` in `app.py`. It only loads into an empty database, so delete `food_app.db` to reload.
- **Look and feel:** edit the colours at the top of `static/style.css`.
- **New page:** add a function with `@app.route("/path")` in `app.py` and a file in `templates/`.
- **Settings:** use environment variables `SECRET_KEY` and `DATABASE_PATH`, never hard-code secrets.

## Ideas for the CI/CD stage
1. On each push: install requirements, run `pytest`.
2. If tests pass: build the Docker image and push it to a registry (e.g. Amazon ECR).
3. Deploy the image (e.g. AWS App Runner / ECS). Point the health check at `/health`.
4. Note: SQLite is a file, so data is lost when a container is replaced unless you attach a volume. For real production, switch to a managed DB (e.g. Amazon RDS) by changing only the DB helper functions in `app.py`.
