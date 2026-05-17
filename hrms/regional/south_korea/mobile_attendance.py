"""
Korea mobile attendance check-in backend.

Public API (whitelisted):
    record_mobile_checkin  — Insert Employee Checkin record via mobile tap.

Contract type: korea_mobile_attendance_record_v1
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import frappe

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTRACT_TYPE = "korea_mobile_attendance_record_v1"

# Distance threshold (metres) beyond which a warning is added.
DISTANCE_WARN_METRES = 500.0

# GPS accuracy threshold (metres) beyond which a warning is added.
ACCURACY_WARN_METRES = 100.0

# Earth radius used for Haversine calculation (WGS-84 mean radius).
EARTH_RADIUS_M = 6_371_008.8

# Valid values for check_type parameter.
VALID_CHECK_TYPES = {"IN", "OUT"}

# Allowed input keys for the whitelisted endpoint.
ALLOWED_PAYLOAD_KEYS = {
    "employee",
    "check_type",
    "timestamp",
    "gps_latitude",
    "gps_longitude",
    "accuracy_meters",
    "selfie_file_doc_name",
    "human_approved",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two GPS coordinates."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _as_float(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        frappe.throw(f"{label} must be a valid number, got: {value!r}")
        raise  # unreachable — frappe.throw raises


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _require_keys(payload: dict, required: set[str], label: str) -> None:
    missing = sorted(k for k in required if k not in payload or payload[k] in (None, ""))
    if missing:
        frappe.throw(f"{label} is missing required fields: {', '.join(missing)}")


def _reject_unknown_keys(payload: dict, allowed: set[str], label: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        frappe.throw(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _get_workplace_coords(employee: str) -> tuple[float, float] | None:
    """Return (latitude, longitude) for the employee's registered Korean workplace.

    Looks up the 'Korea Workplace Profile' custom doctype.  Returns *None* when
    the doctype does not exist or no profile is found for the employee — in that
    case the caller should skip the distance check rather than blocking check-in.
    """
    # Guard: doctype may not be deployed yet.
    if not frappe.db.exists("DocType", "Korea Workplace Profile"):
        return None

    profile_name = frappe.db.get_value(
        "Korea Workplace Profile",
        {"employee": employee, "is_active": 1},
        "name",
        order_by="modified desc",
    )
    if not profile_name:
        return None

    coords = frappe.db.get_value(
        "Korea Workplace Profile",
        profile_name,
        ["workplace_latitude", "workplace_longitude"],
        as_dict=True,
    )
    if not coords:
        return None

    lat = coords.get("workplace_latitude")
    lon = coords.get("workplace_longitude")
    if lat is None or lon is None:
        return None

    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _validate_selfie_file(selfie_file_doc_name: str | None) -> str | None:
    """Verify the File doc exists and return its name, or None if not provided."""
    if not selfie_file_doc_name:
        return None
    if not frappe.db.exists("File", selfie_file_doc_name):
        frappe.throw(f"Selfie file not found: {selfie_file_doc_name!r}")
    return selfie_file_doc_name


def _build_warnings(
    accuracy_meters: float,
    workplace_coords: tuple[float, float] | None,
    gps_latitude: float,
    gps_longitude: float,
) -> tuple[list[str], float | None]:
    """Return (warnings list, distance_from_workplace_meters or None)."""
    warnings: list[str] = []
    distance_metres: float | None = None

    if accuracy_meters > ACCURACY_WARN_METRES:
        warnings.append(
            f"gps_accuracy_low: accuracy_meters={accuracy_meters:.1f} exceeds recommended {ACCURACY_WARN_METRES:.0f}m"
        )

    if workplace_coords is not None:
        distance_metres = _haversine_metres(workplace_coords[0], workplace_coords[1], gps_latitude, gps_longitude)
        if distance_metres > DISTANCE_WARN_METRES:
            warnings.append(
                f"distance_from_workplace: {distance_metres:.1f}m exceeds threshold {DISTANCE_WARN_METRES:.0f}m — flagged for admin review"
            )

    return warnings, distance_metres


# ---------------------------------------------------------------------------
# Public whitelisted endpoint
# ---------------------------------------------------------------------------


@frappe.whitelist()
def record_mobile_checkin(
    employee: str | None = None,
    check_type: str | None = None,
    timestamp: str | None = None,
    gps_latitude: float | str | None = None,
    gps_longitude: float | str | None = None,
    accuracy_meters: float | str | None = None,
    selfie_file_doc_name: str | None = None,
    human_approved: bool | str | None = None,
) -> dict[str, Any]:
    """Record a mobile check-in (IN or OUT) for a Korean employee.

    The caller must pass *human_approved=True*; the UI ensures this is set on
    user tap.  GPS coordinates are validated against the employee's registered
    Korea Workplace Profile if one is configured.  Selfie attachment is optional.

    Returns a contract envelope matching the Phase 3-B spec:
        {
            "contract_type": "korea_mobile_attendance_record_v1",
            "runtime_action": "mobile_checkin",
            "applied": bool,
            "attendance_name": str | None,   # Employee Checkin docname
            "distance_from_workplace_meters": float | None,
            "warning": str | None,           # single human-readable warning (first one)
            "warnings": [...],               # full list for programmatic use
            "data": {
                "employee": str,
                "check_type": "IN" | "OUT",
                "time": str,
                "gps_latitude": float,
                "gps_longitude": float,
                "accuracy_meters": float,
                "selfie_file_doc_name": str | None,
            }
        }
    """
    # ---- Collect into a payload dict for uniform validation ----------------
    payload: dict[str, Any] = {
        "employee": employee,
        "check_type": check_type,
        "timestamp": timestamp,
        "gps_latitude": gps_latitude,
        "gps_longitude": gps_longitude,
        "accuracy_meters": accuracy_meters,
    }
    if selfie_file_doc_name is not None:
        payload["selfie_file_doc_name"] = selfie_file_doc_name
    if human_approved is not None:
        payload["human_approved"] = human_approved

    _reject_unknown_keys(payload, ALLOWED_PAYLOAD_KEYS, "payload")
    _require_keys(
        payload,
        {"employee", "check_type", "timestamp", "gps_latitude", "gps_longitude", "accuracy_meters", "human_approved"},
        "payload",
    )

    # ---- human_approved gate -----------------------------------------------
    if not _coerce_bool(payload.get("human_approved")):
        frappe.throw("human_approved must be true for mobile check-in")

    # ---- Validate employee --------------------------------------------------
    emp = payload["employee"]
    if not frappe.db.exists("Employee", emp):
        frappe.throw(f"Employee not found: {emp!r}")

    # ---- Validate check_type ------------------------------------------------
    ctype = str(payload["check_type"]).upper().strip()
    if ctype not in VALID_CHECK_TYPES:
        frappe.throw(f"check_type must be IN or OUT, got: {payload['check_type']!r}")

    # ---- Parse and validate timestamp --------------------------------------
    ts_raw = payload["timestamp"]
    if isinstance(ts_raw, datetime):
        ts_str = ts_raw.strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts_str = str(ts_raw).strip()
        # Basic format check — Frappe will further validate on insert
        if len(ts_str) < 10:
            frappe.throw(f"timestamp must be a valid datetime string, got: {ts_str!r}")

    # ---- Parse GPS values --------------------------------------------------
    lat = _as_float(payload["gps_latitude"], "gps_latitude")
    lon = _as_float(payload["gps_longitude"], "gps_longitude")
    acc = _as_float(payload["accuracy_meters"], "accuracy_meters")

    if acc < 0:
        frappe.throw("accuracy_meters must be non-negative")

    # ---- Validate lat/lon bounds -------------------------------------------
    if not -90 <= lat <= 90:
        frappe.throw(f"gps_latitude out of range: {lat}")
    if not -180 <= lon <= 180:
        frappe.throw(f"gps_longitude out of range: {lon}")

    # ---- Validate selfie file doc (if provided) ----------------------------
    selfie_name = _validate_selfie_file(payload.get("selfie_file_doc_name"))

    # ---- Compute warnings --------------------------------------------------
    workplace_coords = _get_workplace_coords(emp)
    warnings, distance_metres = _build_warnings(acc, workplace_coords, lat, lon)

    # ---- Insert Employee Checkin record ------------------------------------
    # Frappe uses Employee Checkin (log_type: IN/OUT) for per-tap mobile logs.
    # The daily Attendance summary doctype is rolled up separately by Frappe
    # background jobs — we do not insert into Attendance directly here.
    checkin_doc = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": emp,
            "log_type": ctype,
            "time": ts_str,
            "latitude": lat,
            "longitude": lon,
            "device_id": "korea_mobile_app",
        }
    )
    checkin_doc.insert(ignore_permissions=True)
    checkin_name = checkin_doc.name

    # ---- Attach selfie reference to the checkin doc ------------------------
    if selfie_name:
        try:
            frappe.db.set_value("File", selfie_name, "attached_to_doctype", "Employee Checkin")
            frappe.db.set_value("File", selfie_name, "attached_to_name", checkin_name)
        except Exception:
            frappe.log_error(f"Failed to attach selfie {selfie_name!r} to Employee Checkin {checkin_name!r}")
            warnings.append("selfie_attach_failed: selfie file reference could not be linked — check-in recorded")

    return {
        "contract_type": CONTRACT_TYPE,
        "runtime_action": "mobile_checkin",
        "applied": True,
        "attendance_name": checkin_name,
        "distance_from_workplace_meters": distance_metres,
        "warning": warnings[0] if warnings else None,
        "warnings": warnings,
        "data": {
            "employee": emp,
            "check_type": ctype,
            "time": ts_str,
            "gps_latitude": lat,
            "gps_longitude": lon,
            "accuracy_meters": acc,
            "selfie_file_doc_name": selfie_name,
        },
    }
