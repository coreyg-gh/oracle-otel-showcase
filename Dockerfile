FROM python:3.12-slim

# python-oracledb thin mode does NOT require Oracle Instant Client.
# gcc is only needed if any wheel requires compilation at install time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY report/ ./report/

# Output directory for generated reports (bind-mounted from host)
RUN mkdir -p /reports

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "app.main"]
