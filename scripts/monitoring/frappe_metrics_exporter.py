"""Frappe Prometheus exporter — site metrics.

Mutation boundary: read-only. No .save/.submit/.insert/.delete/.set_value.
Runs as a standalone HTTP server on port 9101 and scrapes Frappe over
the bench `execute` HTTP API or a direct DB connection depending on config.

Exposed metrics
---------------
frappe_active_sites_count                          Gauge
frappe_active_users_per_site{site}                 Gauge
frappe_queue_pending_count{queue}                  Gauge
frappe_db_connection_count{site}                   Gauge
frappe_doctype_record_count{site,doctype}          Gauge
frappe_request_duration_seconds                    Histogram  (*see note)
korea_payroll_closing_draft_pending_count{site}    Gauge
korea_compliance_high_severity_findings{site}      Gauge
korea_attendance_unmarked_count{site}              Gauge

Note on frappe_request_duration_seconds
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A Prometheus pull-based exporter cannot populate request-duration histograms by
itself — duration data must be written per-request via Frappe middleware (hooks).
This exporter registers the Histogram so recording middleware can use the same
metric object via the shared registry; the exporter never populates it directly.
See docs/operations/monitoring.md §"Middleware histogram" for wiring instructions.

Environment variables
---------------------
FRAPPE_SITE_LIST          comma-separated site names (default: all in bench)
FRAPPE_HTTP_HOST          http(s) host of Frappe (default: http://localhost:8000)
FRAPPE_API_KEY            API key for the monitoring user (required in HTTP mode)
FRAPPE_API_SECRET         API secret for the monitoring user (required in HTTP mode)
EXPORTER_PORT             listen port (default: 9101)
EXPORTER_INTERVAL_SECS   scrape collection interval in seconds (default: 15)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

# ---------------------------------------------------------------------------
# Optional Frappe import — framework-free mode supported (bench not required)
# ---------------------------------------------------------------------------
try:
    import frappe  # type: ignore

    _FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
    frappe = None  # type: ignore
    _FRAPPE_AVAILABLE = False

# ---------------------------------------------------------------------------
# prometheus_client
# ---------------------------------------------------------------------------
try:
    from prometheus_client import (
        CollectorRegistry,
        Gauge,
        Histogram,
        start_http_server,
    )

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False

logger = logging.getLogger("frappe_metrics_exporter")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9101"))
EXPORTER_INTERVAL_SECS = int(os.environ.get("EXPORTER_INTERVAL_SECS", "15"))
FRAPPE_HTTP_HOST = os.environ.get("FRAPPE_HTTP_HOST", "http://localhost:8000")
FRAPPE_API_KEY = os.environ.get("FRAPPE_API_KEY", "")
FRAPPE_API_SECRET = os.environ.get("FRAPPE_API_SECRET", "")

_SITE_LIST_ENV = os.environ.get("FRAPPE_SITE_LIST", "")
FRAPPE_SITE_LIST: list[str] = [s.strip() for s in _SITE_LIST_ENV.split(",") if s.strip()]

# DocTypes to count per site
MONITORED_DOCTYPES = ["Salary Slip", "Employee", "Leave Application", "Payroll Entry"]

# Korea payroll closing draft: Payroll Entry rows in Draft status
# (Sessions are in-memory constructs; Draft is the nearest persisted proxy.)
KOREA_PAYROLL_DRAFT_DAYS_THRESHOLD = 7  # alert rule threshold; stored in rules.yml

# ---------------------------------------------------------------------------
# Registry & metric definitions
# ---------------------------------------------------------------------------
if _PROM_AVAILABLE:
    REGISTRY = CollectorRegistry()

    _active_sites = Gauge(
        "frappe_active_sites_count",
        "Number of active Frappe sites",
        registry=REGISTRY,
    )

    _active_users = Gauge(
        "frappe_active_users_per_site",
        "Active sessions / logged-in users per Frappe site",
        labelnames=["site"],
        registry=REGISTRY,
    )

    _queue_pending = Gauge(
        "frappe_queue_pending_count",
        "Number of pending jobs in each Frappe queue",
        labelnames=["queue"],
        registry=REGISTRY,
    )

    _db_connections = Gauge(
        "frappe_db_connection_count",
        "Approximate DB connection count per site (information_schema)",
        labelnames=["site"],
        registry=REGISTRY,
    )

    _doctype_records = Gauge(
        "frappe_doctype_record_count",
        "Total record count for monitored DocTypes",
        labelnames=["site", "doctype"],
        registry=REGISTRY,
    )

    # Histogram — populated by Frappe request middleware, NOT by this collector.
    # Registered here so middleware can use the same metric object.
    _request_duration = Histogram(
        "frappe_request_duration_seconds",
        "HTTP request duration in seconds (populated by Frappe middleware, not by exporter)",
        labelnames=["method", "route", "status"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        registry=REGISTRY,
    )

    _payroll_draft_pending = Gauge(
        "korea_payroll_closing_draft_pending_count",
        "Korea: Payroll Entry rows in Draft status older than threshold days",
        labelnames=["site"],
        registry=REGISTRY,
    )

    _compliance_high = Gauge(
        "korea_compliance_high_severity_findings",
        "Korea: number of high-severity compliance findings from last diagnosis run",
        labelnames=["site"],
        registry=REGISTRY,
    )

    _attendance_unmarked = Gauge(
        "korea_attendance_unmarked_count",
        "Korea: employees with no attendance record for current month",
        labelnames=["site"],
        registry=REGISTRY,
    )
else:
    # Stubs so module can be imported for testing without prometheus_client
    class _Stub:
        def labels(self, **kw):
            return self

        def set(self, v):
            pass

        def observe(self, v):
            pass

    _active_sites = _active_users = _queue_pending = _db_connections = _Stub()  # type: ignore
    _doctype_records = _payroll_draft_pending = _compliance_high = _Stub()  # type: ignore
    _attendance_unmarked = _request_duration = _Stub()  # type: ignore
    REGISTRY = None  # type: ignore


# ---------------------------------------------------------------------------
# Data collection helpers — all read-only
# ---------------------------------------------------------------------------


def _get_sites() -> list[str]:
    """Return site list from env override or bench discovery."""
    if FRAPPE_SITE_LIST:
        return FRAPPE_SITE_LIST
    if _FRAPPE_AVAILABLE and frappe is not None:
        try:
            import subprocess  # noqa: PLC0415

            result = subprocess.run(
                ["bench", "list-sites"],
                capture_output=True, text=True, timeout=10,
            )
            return [s.strip() for s in result.stdout.splitlines() if s.strip()]
        except Exception:
            pass
    return ["localhost"]


def _frappe_db_sql(site: str, query: str, values: tuple = ()) -> list[tuple]:
    """Execute a read-only SQL query against the given site's DB."""
    if not _FRAPPE_AVAILABLE or frappe is None:
        return []
    try:
        frappe.init(site=site)
        frappe.connect()
        rows = frappe.db.sql(query, values)
        frappe.destroy()
        return rows  # type: ignore[return-value]
    except Exception as exc:
        logger.warning("DB query failed for site %s: %s", site, exc)
        try:
            frappe.destroy()
        except Exception:
            pass
        return []


def _collect_active_users(site: str) -> int:
    """Count active user sessions via frappe.sessions table (read-only)."""
    rows = _frappe_db_sql(
        site,
        "SELECT COUNT(*) FROM `tabSessions` WHERE lastupdate > DATE_SUB(NOW(), INTERVAL 30 MINUTE)",
    )
    return int(rows[0][0]) if rows else 0


def _collect_db_connections(site: str) -> int:
    """Approximate DB connection count via information_schema (read-only)."""
    rows = _frappe_db_sql(
        site,
        "SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE Command != 'Sleep'",
    )
    return int(rows[0][0]) if rows else 0


def _collect_doctype_count(site: str, doctype: str) -> int:
    """Count records in a DocType table (read-only)."""
    table = f"tab{doctype}"
    rows = _frappe_db_sql(site, f"SELECT COUNT(*) FROM `{table}`")
    return int(rows[0][0]) if rows else 0


def _collect_queue_pending(site: str) -> dict[str, int]:
    """Read pending job counts from RQ via Redis if available, else 0."""
    queues: dict[str, int] = {"default": 0, "long": 0, "short": 0}
    try:
        import redis  # noqa: PLC0415

        r = redis.Redis.from_url(os.environ.get("REDIS_QUEUE_URL", "redis://localhost:6379"))
        for q in queues:
            queues[q] = r.llen(f"rq:queue:{q}")  # type: ignore[assignment]
    except Exception as exc:
        logger.debug("Redis queue read failed: %s", exc)
    return queues


def _collect_payroll_draft_pending(site: str) -> int:
    """Korea: count Payroll Entry rows in Draft status older than threshold.

    Frappe 'Payroll Entry' is the nearest persisted proxy to a Korea payroll
    closing session in draft state. Sessions themselves are in-memory constructs.
    Read-only: SELECT only.
    """
    rows = _frappe_db_sql(
        site,
        """
        SELECT COUNT(*)
        FROM `tabPayroll Entry`
        WHERE docstatus = 0
          AND creation < DATE_SUB(NOW(), INTERVAL %s DAY)
        """,
        (KOREA_PAYROLL_DRAFT_DAYS_THRESHOLD,),
    )
    return int(rows[0][0]) if rows else 0


def _collect_compliance_high_severity(site: str) -> int:
    """Korea: run compliance diagnosis and return high-severity finding count.

    Compliance diagnosis is ephemeral (no persistence table). We re-run the
    framework-free diagnosis engine on each scrape using the real FrappeDataLoader
    when available (bench present + site initialised). Falls back to a MockLoader
    whose methods all return None, which causes each finding to be flagged
    data_unavailable=True and excluded from the high-severity count — so the
    metric will be 0 rather than silently incorrect.

    Read-only: no DB mutations.
    """
    if not _FRAPPE_AVAILABLE or frappe is None:
        return 0
    try:
        import importlib.util  # noqa: PLC0415
        import pathlib  # noqa: PLC0415

        south_korea_dir = (
            pathlib.Path(__file__).resolve().parent.parent.parent
            / "hrms" / "regional" / "south_korea"
        )
        diag_path = south_korea_dir / "compliance_diagnosis.py"
        if not diag_path.exists():
            return 0

        spec = importlib.util.spec_from_file_location("_compliance_diagnosis", diag_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        # Try to load the real FrappeDataLoader from compliance_diagnosis_api.py.
        # FrappeDataLoader uses frappe.db.get_all / frappe.get_all — read-only.
        # Falls back to MockLoader if import fails (e.g. bench not initialised).
        loader = None
        diag_api_path = south_korea_dir / "compliance_diagnosis_api.py"
        if diag_api_path.exists():
            try:
                api_spec = importlib.util.spec_from_file_location("_compliance_diagnosis_api", diag_api_path)
                api_mod = importlib.util.module_from_spec(api_spec)  # type: ignore[arg-type]
                api_spec.loader.exec_module(api_mod)  # type: ignore[union-attr]
                frappe.init(site=site)
                frappe.connect()
                loader = api_mod.FrappeDataLoader(company=site, workplace="")
            except Exception as init_exc:
                logger.debug("FrappeDataLoader init failed for %s, using MockLoader: %s", site, init_exc)
                try:
                    frappe.destroy()
                except Exception:
                    pass
                loader = None

        if loader is None:
            class _MockLoader:
                """Fallback: all methods return None → findings flagged data_unavailable.

                When this runs, the metric will be 0 (not falsely elevated).
                Wire the real FrappeDataLoader by ensuring the bench site is
                initialised before the exporter runs.
                """
                def get_employees(self): return []
                def get_overtime_hours(self, employee_id, from_date, to_date): return None
                def get_annual_leave_stats(self, employee_id, year): return None
                def get_social_insurance_enrollment(self, employee_id): return None
                def get_last_wage_payment_date(self, employee_id): return None
                def has_anti_bullying_policy(self): return None
            loader = _MockLoader()

        import datetime  # noqa: PLC0415

        result = mod.run_full_compliance_diagnosis(
            company=site,
            workplace="",
            as_of_date=datetime.date.today().isoformat(),
            data_loader=loader,
        )
        try:
            frappe.destroy()
        except Exception:
            pass
        findings = result.get("findings", [])
        return sum(1 for f in findings if f.get("severity") == "high" and not f.get("data_unavailable"))
    except Exception as exc:
        logger.warning("Compliance diagnosis failed for site %s: %s", site, exc)
        try:
            frappe.destroy()
        except Exception:
            pass
        return 0


def _collect_attendance_unmarked(site: str) -> int:
    """Korea: employees with no Attendance record for current calendar month.

    Uses a LEFT JOIN to find employees with no attendance rows this month.
    Read-only: SELECT only.
    """
    rows = _frappe_db_sql(
        site,
        """
        SELECT COUNT(e.name)
        FROM `tabEmployee` e
        LEFT JOIN `tabAttendance` a
            ON a.employee = e.name
            AND a.attendance_date >= DATE_FORMAT(NOW(), '%%Y-%%m-01')
            AND a.attendance_date < DATE_FORMAT(DATE_ADD(NOW(), INTERVAL 1 MONTH), '%%Y-%%m-01')
            AND a.docstatus = 1
        WHERE e.status = 'Active'
          AND a.name IS NULL
        """,
    )
    return int(rows[0][0]) if rows else 0


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------


def collect_all() -> None:
    """Collect all metrics and set gauge values. Called every EXPORTER_INTERVAL_SECS."""
    sites = _get_sites()
    _active_sites.set(len(sites))

    # Queue counts are global (not per-site in single-Redis setups)
    queue_counts = _collect_queue_pending(sites[0] if sites else "localhost")
    for q, count in queue_counts.items():
        _queue_pending.labels(queue=q).set(count)

    for site in sites:
        logger.debug("Collecting metrics for site: %s", site)

        try:
            _active_users.labels(site=site).set(_collect_active_users(site))
        except Exception as exc:
            logger.warning("active_users failed [%s]: %s", site, exc)

        try:
            _db_connections.labels(site=site).set(_collect_db_connections(site))
        except Exception as exc:
            logger.warning("db_connections failed [%s]: %s", site, exc)

        for doctype in MONITORED_DOCTYPES:
            try:
                count = _collect_doctype_count(site, doctype)
                _doctype_records.labels(site=site, doctype=doctype).set(count)
            except Exception as exc:
                logger.warning("doctype_count[%s] failed [%s]: %s", doctype, site, exc)

        try:
            _payroll_draft_pending.labels(site=site).set(_collect_payroll_draft_pending(site))
        except Exception as exc:
            logger.warning("payroll_draft_pending failed [%s]: %s", site, exc)

        try:
            _compliance_high.labels(site=site).set(_collect_compliance_high_severity(site))
        except Exception as exc:
            logger.warning("compliance_high_severity failed [%s]: %s", site, exc)

        try:
            _attendance_unmarked.labels(site=site).set(_collect_attendance_unmarked(site))
        except Exception as exc:
            logger.warning("attendance_unmarked failed [%s]: %s", site, exc)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not _PROM_AVAILABLE:
        logger.error("prometheus_client not installed. pip install prometheus-client")
        raise SystemExit(1)

    logger.info("Starting Frappe metrics exporter on port %d", EXPORTER_PORT)
    start_http_server(EXPORTER_PORT, registry=REGISTRY)

    while True:
        try:
            collect_all()
        except Exception as exc:
            logger.exception("Collection cycle failed: %s", exc)
        time.sleep(EXPORTER_INTERVAL_SECS)


if __name__ == "__main__":
    main()
