FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install CA certificates for outbound HTTPS calls.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN update-ca-certificates

# Create runtime directories.
RUN mkdir -p /app/logs /app/media /app/static

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput --settings=config.settings.prod || true

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput --settings=config.settings.prod; gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
