FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY mitacs_scraper/requirements.txt /app/mitacs_scraper/requirements.txt

RUN pip install --no-cache-dir -r /app/mitacs_scraper/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . /app

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "mitacs_scraper.ui_app:app", "--workers", "1", "--threads", "8", "--timeout", "300"]
