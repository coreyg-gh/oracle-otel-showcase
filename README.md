# Oracle 26ai + OpenTelemetry Showcase

A self-contained observability demo for **Oracle Database 26ai** using the **OpenTelemetry** standard from Python.
The stack runs entirely in Docker Compose and includes a live Grafana dashboard and an on-demand HTML/Markdown report generator.

---

## What This Demonstrates

| Area | Details |
|------|---------|
| **Oracle 26ai AI Vector Search** | Insert and query 1536-dim vectors using `VECTOR(1536, FLOAT32)` and `VECTOR_DISTANCE(..., COSINE)` |
| **OTel DBAPI Instrumentation** | Every `cursor.execute()` call produces a child span with `db.system`, `db.statement`, and `db.name` attributes |
| **Custom OTel Metrics** | Pool utilisation gauges, query latency histograms, vector similarity histograms, error counters |
| **OTel Collector** | Single pipeline: app → Collector → Prometheus (metrics) + Tempo (traces) |
| **Grafana Dashboard** | Pre-provisioned, 5-second refresh, jump from metric spike to exact Tempo trace |
| **Report Generator** | Queries Prometheus HTTP API + Tempo Search API → renders HTML + Markdown |
| **python-oracledb thin mode** | No Oracle Instant Client required — pure Python driver |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Docker Compose                                                    │
│                                                                    │
│  ┌─────────────────┐   OTLP gRPC    ┌──────────────────────┐     │
│  │  Python App     │ ─────────────▶ │  OTel Collector      │     │
│  │  python-oracledb│                │  :4317 (gRPC)        │     │
│  │  OTel SDK       │                └──────┬───────────────┘     │
│  └────────┬────────┘                       │                      │
│           │ SQL                   ┌─────────▼──────────┐         │
│           │                       │  Prometheus         │         │
│  ┌────────▼────────┐              │  :9090              │         │
│  │  Oracle Free    │              └─────────┬──────────┘         │
│  │  26ai :1521     │              ┌─────────▼──────────┐         │
│  │  CRUD + VECTOR  │              │  Grafana Tempo      │         │
│  └─────────────────┘              │  :3200              │         │
│                                   └─────────┬──────────┘         │
│                                   ┌─────────▼──────────┐         │
│  ┌─────────────────┐              │  Grafana            │         │
│  │  Report Gen     │ ──query──▶   │  :3000              │         │
│  │  (on-demand)    │              └────────────────────┘         │
│  └─────────────────┘                                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **Docker Desktop 4.x+** with at least **8 GB RAM** allocated
- **Oracle Container Registry access** (free, required for Oracle Free image)

### Step 1 — Oracle Container Registry login (REQUIRED)

The Oracle Free database image is hosted on Oracle's private registry. You must authenticate before `docker compose up` will work.

> **Important (from June 30, 2025):** Oracle Container Registry **no longer accepts your account password**. You must use an **auth token** as the password. Follow the steps below.

#### 1a — Create a free Oracle account and accept terms

1. Create a free Oracle account at <https://profile.oracle.com> (if you don't have one)
2. Accept the **Oracle Standard Terms and Restrictions** for `database/free`:
   - Go to <https://container-registry.oracle.com>
   - Navigate to **Database** → **free** → click **Continue** to accept terms

#### 1b — Generate an auth token

1. Sign in to <https://container-registry.oracle.com>
2. Click your **profile name** in the top-right corner
3. Select **Auth Token** from the profile menu
4. Click **Generate Secret Key**
5. **Copy the key immediately** — it is only shown once. If you lose it, delete it and generate a new one.

#### 1c — Log in from your terminal

```bash
docker login container-registry.oracle.com
# Username: your Oracle SSO username (email)
# Password: paste the auth token generated above (NOT your account password)
```

> **Note:** Without this step, `docker compose up` will fail with a `401 Unauthorized` error when pulling the Oracle image.

---

## Publishing to GitHub (first time setup)

Follow these steps if you are setting this project up for the first time and want to publish it to your own GitHub account.

### Step 2 — Install Git

Skip this step if `git --version` already works in your terminal.

**macOS**
```bash
# Install via Homebrew (recommended)
brew install git

# Or install Xcode Command Line Tools (includes git)
xcode-select --install
```

**Windows**
1. Download Git from <https://git-scm.com/download/win>
2. Run the installer, accepting all defaults
3. Open **Git Bash** or **Windows Terminal** for all commands below

**Linux (Debian/Ubuntu)**
```bash
sudo apt update && sudo apt install -y git
```

Verify the installation:
```bash
git --version
# Expected output: git version 2.x.x
```

### Step 3 — Configure Git identity (once per machine)

```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

### Step 4 — Create a GitHub account

Skip this step if you already have a GitHub account.

1. Go to <https://github.com> and click **Sign up**
2. Complete the registration (free plan is sufficient)
3. Note your **username** — you will use it in the next step

### Step 5 — Create an empty GitHub repository

1. Sign in to <https://github.com>
2. Click the **+** icon in the top-right corner → **New repository**
3. Fill in:
   - **Repository name:** `oracle-otel-showcase`
   - **Description:** `Oracle 26ai + OpenTelemetry observability showcase` (optional)
   - **Visibility:** Public _(required to showcase your work)_
4. **Leave all checkboxes unticked** — do NOT add a README, .gitignore, or licence. The repo must be completely empty so there are no conflicts.
5. Click **Create repository**

GitHub will show you a page with setup instructions — you can ignore those and follow the steps below instead.

### Step 6 — Initialise and push the local project

Open a terminal in the project directory (wherever you downloaded or created it) and run:

```bash
# Initialise a local git repository
git init

# Stage all project files
git add .

# Create the first commit
git commit -m "Initial commit: Oracle 26ai + OpenTelemetry showcase"

# Rename the default branch to main (GitHub standard)
git branch -M main

# Add your GitHub repo as the remote origin
# Replace YOUR_USERNAME with your actual GitHub username
git remote add origin https://github.com/YOUR_USERNAME/oracle-otel-showcase.git

# Push and set the upstream tracking branch
git push -u origin main
```

After the push completes, visit `https://github.com/YOUR_USERNAME/oracle-otel-showcase` — your project will be live.

> **Tip:** If GitHub asks for credentials during `git push`, use your GitHub username and a **Personal Access Token** (not your GitHub password). Create one at <https://github.com/settings/tokens> → **Generate new token (classic)** → tick the **repo** scope.

### Step 7 — Future changes

Once the remote is set up, pushing subsequent changes is:

```bash
git add .
git commit -m "Describe your change"
git push
```

---

## Quick Start (running the stack locally)

Before running, complete Steps 1–7 above (Oracle Container Registry login + GitHub setup).

```bash
# 1. Enter the project directory (or clone from GitHub if starting fresh)
#    Replace YOUR_USERNAME with your actual GitHub username
git clone https://github.com/YOUR_USERNAME/oracle-otel-showcase.git
cd oracle-otel-showcase

# 2. (Optional) copy and customise environment variables
cp .env.example .env

# 3. Start the full stack
docker compose up -d

# 4. Wait ~2 minutes for Oracle Free to initialise on first boot
docker compose logs -f app   # Watch until you see "Workload runner starting"

# 5. Open Grafana (no login required)
open http://localhost:3000
# Navigate to Dashboards → Oracle → "Oracle 26ai + OpenTelemetry"
```

The dashboard auto-refreshes every 5 seconds. You should see live data within 30 seconds of the app starting.

---

## Generating a Report

The report generator queries the last 30 minutes of Prometheus metrics and Tempo traces and produces HTML and Markdown files:

```bash
docker compose --profile report up report-generator
```

Reports are written to `./reports/`. Open the `.html` file in your browser for the full interactive version.

```bash
open reports/report_*.html
```

To customise the lookback window:

```bash
REPORT_LOOKBACK_MINUTES=60 docker compose --profile report up report-generator
```

---

## Project Structure

```
oracle-otel-showcase/
├── app/                        # Python workload application
│   ├── main.py                 # Entry point
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── database/
│   │   ├── connection.py       # Pool factory + OTel gauge callbacks
│   │   └── schema.py           # DDL + seed data (idempotent)
│   ├── otel/
│   │   ├── setup.py            # TracerProvider + MeterProvider
│   │   ├── metrics.py          # Custom metric instruments
│   │   └── dbapi_patch.py      # DBAPI connection instrumentation
│   └── workloads/
│       ├── runner.py           # asyncio orchestrator
│       ├── crud.py             # INSERT / SELECT / UPDATE / DELETE
│       ├── vector_search.py    # Oracle 26ai VECTOR_DISTANCE queries
│       └── pool_monitor.py     # Pool stats + concurrent connection demo
├── report/                     # On-demand report generator
│   ├── generator.py
│   ├── prometheus_client.py
│   ├── tempo_client.py
│   └── templates/
│       ├── report.html.j2      # Dark-themed interactive HTML report
│       └── report.md.j2        # Markdown report
├── otel-collector/config.yaml  # Collector: OTLP → Prometheus + Tempo
├── prometheus/prometheus.yml
├── tempo/tempo.yaml
├── grafana/
│   ├── provisioning/           # Auto-provisioned datasources + dashboards
│   └── dashboards/oracle-otel.json
├── tests/                      # pytest tests (no Oracle required)
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Dashboard Panels

| Panel | Description |
|-------|-------------|
| Ops / sec | Total Oracle operations per second |
| Error Rate | Errors per second (turns red > 1/s) |
| Query p95 Latency | 95th percentile across all operations |
| Pool Busy | Current connections in use (gauge) |
| Vector Similarity p50 | Median cosine similarity from ANN searches |
| Query Duration by Operation | p50 / p95 / p99 time series per op type |
| Operations / sec by Type | INSERT / SELECT / UPDATE / DELETE / vector_search breakdown |
| Pool Connections Over Time | Pool size vs busy connections |
| Pool Utilisation % | busy / size ratio |
| Vector Search Latency | p50 + p95 for vector_search operations only |
| Vector Similarity Distribution | p50 + p90 cosine similarity over time |
| Recent Traces | Tempo embedded trace list (click to drill into spans) |

---

## Key Technical Notes

### Oracle 26ai Vector Search from Python

The Oracle 26ai `VECTOR` data type requires a specific Python binding:

```python
import array
import numpy as np
import oracledb

# numpy array → array.array('f') required for python-oracledb VECTOR binding
vec = array.array('f', embedding.astype(np.float32).tolist())

# ANN search with HNSW index
cursor.execute("""
    SELECT product_id, VECTOR_DISTANCE(embedding, :q, COSINE) AS distance
    FROM product_embeddings
    ORDER BY distance ASC
    FETCH FIRST 5 ROWS ONLY
""", q=vec)
```

> `np.ndarray` cannot be passed directly — it must be converted to `array.array('f', ...)`.

### OTel DBAPI Instrumentation

`opentelemetry-instrumentation-dbapi` wraps any PEP 249 DB-API connection, automatically creating a child span for every `cursor.execute()` call:

```python
from opentelemetry.instrumentation.dbapi import DatabaseApiIntegration

integration = DatabaseApiIntegration(tracer_provider=tp, database_component="oracle")
instrumented_conn = integration.wrapped_connection(lambda: raw_conn, args=(), kwargs={})
```

Each span includes `db.system=oracle`, `db.statement=<sql>`, and `db.name=<service_name>`.

### Metric Naming

The OTel Collector exports metrics to Prometheus with the `oracle_otel` namespace prefix:

| OTel metric name | Prometheus name |
|-----------------|-----------------|
| `oracle.query.duration` | `oracle_otel_oracle_query_duration_ms_bucket` |
| `oracle.pool.busy` | `oracle_otel_oracle_pool_busy_connections` |
| `oracle.db.operations` | `oracle_otel_oracle_db_operations_total` |
| `oracle.vector.similarity_score` | `oracle_otel_oracle_vector_similarity_score_1_bucket` |

---

## Development

### Running tests (no Oracle required)

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

### Linting

```bash
ruff check .
ruff format .
```

### Connecting to an external Oracle instance

Override the Oracle environment variables:

```bash
ORACLE_HOST=my-oracle-host.example.com \
ORACLE_SERVICE=MYPDB \
ORACLE_USER=myuser \
ORACLE_PASSWORD=mypassword \
ORACLE_SYSTEM_PASSWORD=syspassword \
docker compose up app
```

Or set them in `.env`.

---

## References

- [ODP.NET OpenTelemetry Documentation (Oracle DB 26)](https://docs.oracle.com/en/database/oracle/oracle-database/26/odpnt/featOpenTelemetry.html)
- [Application Monitoring with OpenTelemetry (Oracle Blog)](https://blogs.oracle.com/observability/application-monitoring-with-opentelemetry)
- [python-oracledb — Oracle 26ai Vector Support](https://python-oracledb.readthedocs.io/en/latest/user_guide/vector_data_type.html)
- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/)

---

## License

MIT
