FROM python:3.12-slim
RUN apt-get update && apt-get install -y \
    libpq-dev gcc docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["gunicorn", "-w", "4", "--threads", "16", "-b", "0.0.0.0:5000", "--timeout", "180", "--graceful-timeout", "30", "--preload", "--chdir", "/app", "run:app"]