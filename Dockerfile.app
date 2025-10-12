FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt /app/app-requirements.txt
RUN pip install --no-cache-dir -r /app/app-requirements.txt

COPY app /app/app

EXPOSE 8000
CMD ["python", "-m", "app.main"]


