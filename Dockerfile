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
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 8000

# SingleInstance EB environment: API and the SQS worker both run in this one container,
# supervised as separate processes so one restarting doesn't take down the other.
# entrypoint.sh runs `alembic upgrade head` first, before either process starts.
CMD ["./entrypoint.sh"]
