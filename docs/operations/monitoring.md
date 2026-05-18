# Frappe HRMS Korea — Monitoring Operations Guide

Self-hosted observability stack: Prometheus + Loki + Grafana + Alertmanager.
No external LLM API. Read-only observation — zero mutation of Frappe data.

---

## Stack overview

| Service | Port | Purpose |
|---|---|---|
| Prometheus | 9090 | Metrics collection and alerting |
| Alertmanager | 9093 | Alert routing → Telegram |
| Loki | 3100 | Log aggregation |
| Promtail | — | Log shipper (bench logs → Loki) |
| Grafana | 3000 | Dashboards |
| Frappe exporter | 9101 | Custom Frappe metrics |
| Alert webhook | 5001 | Alertmanager → Telegram bridge |

---

## Quick start

```bash
# Copy and fill env file
cp docker/monitoring/.env.example docker/monitoring/.env
# Edit: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GRAFANA_ADMIN_PASSWORD

# Start the full stack
docker compose -f docker/monitoring/docker-compose.yml up -d

# Verify all services healthy
docker compose -f docker/monitoring/docker-compose.yml ps
```

URLs after startup:
- Grafana: http://localhost:3000 (admin / value from .env)
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

---

## Environment variables

Create `docker/monitoring/.env` with the following values:

```env
# Required
TELEGRAM_BOT_TOKEN=<bot_token_from_botfather>
TELEGRAM_CHAT_ID=<target_chat_id>

# Optional — defaults shown
GRAFANA_ADMIN_PASSWORD=admin
GRAFANA_ROOT_URL=http://localhost:3000
FRAPPE_SITE_LIST=localhost
FRAPPE_HTTP_HOST=http://frappe:8000
FRAPPE_API_KEY=
FRAPPE_API_SECRET=
REDIS_QUEUE_URL=redis://redis:6379
WEBHOOK_SECRET=
```

Never commit the `.env` file to the repository.

---

## Frappe exporter

File: `scripts/monitoring/frappe_metrics_exporter.py`

The exporter polls Frappe every 15 seconds (configurable via `EXPORTER_INTERVAL_SECS`)
and exposes metrics on port 9101 (`/metrics`).

### Metrics reference

| Metric | Type | Description |
|---|---|---|
| `frappe_active_sites_count` | Gauge | Number of active Frappe sites |
| `frappe_active_users_per_site{site}` | Gauge | Sessions active in last 30 min |
| `frappe_queue_pending_count{queue}` | Gauge | Pending jobs per RQ queue |
| `frappe_db_connection_count{site}` | Gauge | Active DB connections |
| `frappe_doctype_record_count{site,doctype}` | Gauge | Total records per DocType |
| `frappe_request_duration_seconds{method,route,status}` | Histogram | Per-request duration (see below) |
| `korea_payroll_closing_draft_pending_count{site}` | Gauge | Payroll Entry drafts older than 7d |
| `korea_compliance_high_severity_findings{site}` | Gauge | High-severity compliance findings |
| `korea_attendance_unmarked_count{site}` | Gauge | Active employees missing attendance |

### Middleware histogram

`frappe_request_duration_seconds` is registered in the exporter's registry so
that future integrations can reference the metric name in Grafana queries.
However, a pull-based exporter runs in a **separate process** from Frappe — it
cannot share in-memory metric objects with the Frappe WSGI process.

To actually populate this histogram, one of these approaches is required:

1. **Frappe native Prometheus endpoint** — embed `prometheus_client`'s WSGI
   middleware directly in the Frappe application and expose `/metrics` there.
   Prometheus would then scrape Frappe directly rather than the exporter.

2. **Node-exporter textfile collector** — Frappe middleware writes per-request
   summary stats to a `.prom` file; the node-exporter reads it on the next
   scrape cycle (eventual consistency, no sub-second granularity).

Until one of these is implemented, `frappe_request_duration_seconds` will have
no observations. All other metrics work without it.

### Running the exporter standalone (without Docker)

```bash
pip install prometheus-client redis
FRAPPE_SITE_LIST=mysite.local EXPORTER_PORT=9101 python scripts/monitoring/frappe_metrics_exporter.py
```

---

## Alertmanager → Telegram webhook

File: `scripts/monitoring/alert_webhook.py`

Receives Alertmanager v4 POST payloads and forwards formatted messages to
a Telegram chat. Runs on port 5001.

### Alert message format

```
🔴 [FIRING] 🚨 FrappeExporterDown
Instance: frappe-exporter:9101
Summary: Frappe metrics exporter is down
Detail: The Frappe metrics exporter has been unreachable for 5+ minutes.
```

Resolved alerts are prefixed with `✅ [RESOLVED]`.

### Running standalone

```bash
TELEGRAM_BOT_TOKEN=<token> TELEGRAM_CHAT_ID=<chat_id> python scripts/monitoring/alert_webhook.py
```

Health check: `curl http://localhost:5001/`

---

## Alert rules

File: `docker/monitoring/prometheus/rules.yml`

### Active rules

| Alert | Condition | Severity | For |
|---|---|---|---|
| `FrappeExporterDown` | exporter unreachable | critical | 5m |
| `FrappeDbConnectionsHigh` | connections > 80 | warning | 5m |
| `FrappeQueuePendingHigh` | queue pending > 500 | warning | 5m |
| `FrappeQueuePendingCritical` | queue pending > 2000 | critical | 2m |
| `KoreaPayrollClosingDraftPending` | draft Payroll Entry > 7d | warning | 1m |
| `KoreaComplianceHighSeverity` | high findings > 3 | warning | 5m |
| `KoreaComplianceHighSeverityCritical` | high findings > 10 | critical | 5m |
| `KoreaAttendanceUnmarked` | unmarked employees > 10 | warning | 30m |
| `CronJobStale` | last success > 1h ago | warning | 5m |
| `CronJobConsecutiveFailures` | failures > 2 | warning | 1m |

Adjust thresholds in `rules.yml` to match your environment.

---

## Grafana dashboards

Provisioned automatically from `docker/monitoring/grafana/dashboards/`.
Available under folder **"Frappe HRMS Korea"** in Grafana.

| Dashboard | UID | Purpose |
|---|---|---|
| Frappe HRMS — Infrastructure Overview | `frappe-overview-v1` | Site health, users, queues, DB, logs |
| Korea HRMS — Business Metrics | `korea-hrms-business-v1` | Payroll, compliance, attendance KPIs |
| Cron / Scheduler Health | `cron-health-v1` | Cron job last-success and failure counts |

Default home dashboard: Frappe HRMS Infrastructure Overview.

### Editing dashboards

1. Edit in the Grafana UI.
2. Export JSON (`Dashboard → Share → Export → Save to file`).
3. Replace the corresponding file in `docker/monitoring/grafana/dashboards/`.
4. `docker compose restart grafana` (or wait up to 30 seconds for auto-reload).

---

## Loki log aggregation

### Log sources

| Source | Labels |
|---|---|
| Frappe bench logs (`/home/frappe/frappe-bench/logs/*.log`) | `job=frappe` |
| Docker container logs | `container`, `service`, `compose_project` |

### Useful LogQL queries

```logql
# Frappe errors in last 1h
{job="frappe"} |= "ERROR"

# Slow requests (>2s)
{job="frappe"} |= "Request took"

# Cron/scheduler log lines
{job="frappe"} |= "cron" or {job="frappe"} |= "scheduler"

# MariaDB errors
{container="frappe_mariadb"} |= "ERROR"
```

### Log retention

Default retention: 14 days (336h). Adjust in `loki/loki-config.yml`:
```yaml
limits_config:
  retention_period: 336h  # change as needed
```

---

## Cron health textfile collector

The `cron_health.json` dashboard uses two metrics that require the
**node-exporter textfile collector**:
- `cron_last_success_timestamp_seconds{job="..."}`
- `cron_consecutive_failures{job="..."}`

These are **not** populated by the Frappe exporter. Each cron/scheduled
job must write a snippet to the textfile directory when it runs.

### Setup

1. Add node-exporter to `docker-compose.yml` with:
   ```yaml
   node-exporter:
     image: prom/node-exporter:v1.8.0
     volumes:
       - /proc:/host/proc:ro
       - /sys:/host/sys:ro
       - /var/monitoring/textfiles:/textfiles:ro
     command:
       - "--collector.textfile.directory=/textfiles"
   ```

2. Add the node-exporter scrape job to `prometheus.yml` (see commented section).

3. Each cron job writes a snippet at run time:

```python
# Example: scripts/hermes_cron_seed.py (or any scheduled script)
import pathlib, time

TEXTFILE_DIR = pathlib.Path("/var/monitoring/textfiles")
JOB_NAME = "hermes_korea_seed"

def write_cron_success():
    snippet = f"""
# HELP cron_last_success_timestamp_seconds Unix timestamp of last successful run
# TYPE cron_last_success_timestamp_seconds gauge
cron_last_success_timestamp_seconds{{job="{JOB_NAME}"}} {time.time()}
# HELP cron_consecutive_failures Consecutive failure count (reset to 0 on success)
# TYPE cron_consecutive_failures gauge
cron_consecutive_failures{{job="{JOB_NAME}"}} 0
"""
    TEXTFILE_DIR.mkdir(parents=True, exist_ok=True)
    (TEXTFILE_DIR / f"{JOB_NAME}.prom").write_text(snippet.strip())

def write_cron_failure(failures: int):
    snippet = f"""
cron_consecutive_failures{{job="{JOB_NAME}"}} {failures}
"""
    TEXTFILE_DIR.mkdir(parents=True, exist_ok=True)
    (TEXTFILE_DIR / f"{JOB_NAME}_failures.prom").write_text(snippet.strip())
```

Until the textfile collector is set up, the cron_health dashboard panels
will show "No data" — this is expected and non-breaking.

---

## Troubleshooting

### Grafana shows "No data" for Frappe metrics

1. Check exporter is running: `docker compose logs frappe-exporter`
2. Verify exporter scrape target is UP in Prometheus → Status → Targets
3. Confirm `FRAPPE_SITE_LIST` matches your actual site name

### Alerts not reaching Telegram

1. Test webhook directly:
   ```bash
   curl -X POST http://localhost:5001/ \
     -H "Content-Type: application/json" \
     -d '{"status":"firing","alerts":[{"status":"firing","labels":{"alertname":"Test"},"annotations":{"summary":"Test alert"}}]}'
   ```
2. Check webhook logs: `docker compose logs alert-webhook`
3. Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`

### Loki not receiving logs

1. Check Promtail: `docker compose logs promtail`
2. Verify the bench log path in `promtail-config.yml` matches your actual bench location
3. Check Docker socket permission: Promtail needs read access to `/var/run/docker.sock`

### Prometheus scrape failing for frappe-exporter

The exporter starts an HTTP server and requires `prometheus-client` to be
installed. The Docker container installs it at startup via pip. On first start
this may take 10–20 seconds — the scrape target will show as DOWN briefly.

---

## File structure

```
docker/monitoring/
├── docker-compose.yml
├── .env.example                      (create .env from this)
├── prometheus/
│   ├── prometheus.yml
│   └── rules.yml
├── loki/
│   ├── loki-config.yml
│   └── promtail-config.yml
├── alertmanager/
│   └── alertmanager.yml
└── grafana/
    ├── provisioning/
    │   ├── datasources.yml
    │   └── dashboards.yml
    └── dashboards/
        ├── frappe_overview.json
        ├── korea_hrms_business.json
        └── cron_health.json

scripts/monitoring/
├── frappe_metrics_exporter.py
└── alert_webhook.py
```
