FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . supervisor

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY supervisord.conf ./

EXPOSE 8000

# SingleInstance EB environment: API and the SQS worker both run in this one container,
# supervised as separate processes so one restarting doesn't take down the other.
CMD ["supervisord", "-c", "supervisord.conf"]
