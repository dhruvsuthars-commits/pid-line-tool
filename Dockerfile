FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY pid-line-tool/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY pid-line-tool/ .

# Cloud Run expects the app to bind to $PORT
ENV PORT=8080
EXPOSE ${PORT}

# Use Gunicorn for production
CMD ["gunicorn", "-w", "2", "-k", "gthread", "--threads", "4", "-b", ":${PORT}", "app:app"]
