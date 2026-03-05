"""
Stock Alerts — Strain watchlist and restock notifications.

Users can subscribe to strain alerts via the API.  After each stock index
rebuild, the alert checker compares the new index against active watchlist
entries and sends email notifications when a watched strain is found in stock.

Storage: alerts are persisted as a JSON file in Azure Blob Storage alongside
the stock index, at  stock-index/alerts.json.

Copyright (c) 2026 Acidni LLC
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALERTS_BLOB_PATH = "jsonfiles/stock-index/alerts.json"
CONTAINER_NAME = "terprint"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_blob_container():
    """Get the blob container client."""
    try:
        from azure.storage.blob import BlobServiceClient

        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            logger.warning("AZURE_STORAGE_CONNECTION_STRING not set — alerts unavailable")
            return None
        client = BlobServiceClient.from_connection_string(conn_str)
        return client.get_container_client(CONTAINER_NAME)
    except Exception as e:
        logger.error(f"Failed to create blob container client: {e}")
        return None


def _load_alerts() -> list[dict]:
    """Load all alert subscriptions from blob storage."""
    container = _get_blob_container()
    if not container:
        return []
    try:
        blob = container.get_blob_client(ALERTS_BLOB_PATH)
        content = blob.download_blob().readall()
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception:
        # File doesn't exist yet — that's fine
        return []


def _save_alerts(alerts: list[dict]) -> bool:
    """Persist alert subscriptions to blob storage."""
    container = _get_blob_container()
    if not container:
        return False
    try:
        blob = container.get_blob_client(ALERTS_BLOB_PATH)
        blob.upload_blob(json.dumps(alerts, indent=2, default=str), overwrite=True)
        return True
    except Exception as e:
        logger.error(f"Failed to save alerts: {e}")
        return False


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------

def create_alert(
    email: str,
    strain: str,
    strain_slug: str,
    dispensary: str | None = None,
    max_distance_miles: float | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """Create a new strain alert subscription.

    Returns the created alert dict.
    """
    alerts = _load_alerts()

    # Check for duplicate
    for a in alerts:
        if (
            a.get("email", "").lower() == email.lower()
            and a.get("strain_slug") == strain_slug
            and a.get("dispensary") == dispensary
        ):
            return {**a, "_duplicate": True}

    alert = {
        "id": str(uuid.uuid4())[:8],
        "email": email.lower().strip(),
        "strain": strain,
        "strain_slug": strain_slug,
        "dispensary": dispensary,
        "max_distance_miles": max_distance_miles,
        "lat": lat,
        "lng": lng,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_notified": None,
        "active": True,
    }
    alerts.append(alert)
    _save_alerts(alerts)
    logger.info(f"Created alert {alert['id']}: {email} watching '{strain}' (dispensary={dispensary})")
    return alert


def get_alerts_for_email(email: str) -> list[dict]:
    """Get all active alerts for a specific email."""
    alerts = _load_alerts()
    return [a for a in alerts if a.get("email", "").lower() == email.lower() and a.get("active")]


def delete_alert(alert_id: str) -> bool:
    """Deactivate an alert by ID."""
    alerts = _load_alerts()
    found = False
    for a in alerts:
        if a.get("id") == alert_id:
            a["active"] = False
            found = True
            break
    if found:
        _save_alerts(alerts)
        logger.info(f"Deactivated alert {alert_id}")
    return found


def get_all_active_alerts() -> list[dict]:
    """Get all active alerts across all users."""
    return [a for a in _load_alerts() if a.get("active")]


# ---------------------------------------------------------------------------
# Alert Checker — called after stock index rebuild
# ---------------------------------------------------------------------------

def check_alerts_against_index(index: dict) -> dict:
    """
    Compare active alerts against the current stock index.
    Sends email notifications for any matched strains.

    Args:
        index: The full stock index dict (with by_strain, by_dispensary, etc.)

    Returns:
        Summary dict with matches found, emails sent, etc.
    """
    from notifications import send_email

    alerts = get_all_active_alerts()
    if not alerts:
        logger.info("No active stock alerts to check")
        return {"active_alerts": 0, "matches": 0, "emails_sent": 0}

    by_strain = index.get("by_strain", {})
    now = datetime.now(timezone.utc)
    matches_found = 0
    emails_sent = 0
    match_details: list[dict] = []

    # Group alerts by email for batched notifications
    email_matches: dict[str, list[dict]] = {}

    for alert in alerts:
        strain_slug = alert.get("strain_slug", "")
        target_dispensary = alert.get("dispensary")

        # Exact match first
        items = by_strain.get(strain_slug, [])
        # Substring match if no exact
        if not items:
            for slug, slug_items in by_strain.items():
                if strain_slug in slug or slug in strain_slug:
                    items.extend(slug_items)

        if not items:
            continue

        # Filter by dispensary if specified
        if target_dispensary:
            items = [i for i in items if i.get("dispensary", "").lower() == target_dispensary.lower()]

        # Filter by distance if geo-location provided
        if alert.get("lat") and alert.get("lng") and alert.get("max_distance_miles"):
            from stock_indexer import StockIndexer

            filtered = []
            for item in items:
                store = item.get("store", {})
                item_lat = store.get("latitude")
                item_lng = store.get("longitude")
                if item_lat and item_lng:
                    dist = StockIndexer.calculate_distance(
                        alert["lat"], alert["lng"], item_lat, item_lng
                    )
                    if dist <= alert["max_distance_miles"]:
                        item["distance_miles"] = round(dist, 1)
                        filtered.append(item)
            items = filtered

        if items:
            matches_found += 1
            email = alert["email"]
            if email not in email_matches:
                email_matches[email] = []
            email_matches[email].append({
                "alert": alert,
                "items": items[:10],  # cap per-alert items for email readability
            })

    # Send batched notification emails
    for email, alert_matches in email_matches.items():
        subject = f"🌿 Terprint Stock Alert: {len(alert_matches)} strain(s) found in stock!"
        body = _build_alert_email(alert_matches, now)
        success = send_email(subject, body, recipient=email)
        if success:
            emails_sent += 1
            # Update last_notified timestamp
            _update_last_notified([m["alert"]["id"] for m in alert_matches])

    logger.info(
        f"Stock alert check: {len(alerts)} active alerts, "
        f"{matches_found} matches, {emails_sent} emails sent"
    )
    return {
        "active_alerts": len(alerts),
        "matches": matches_found,
        "emails_sent": emails_sent,
    }


def _build_alert_email(alert_matches: list[dict], now: datetime) -> str:
    """Build a nicely formatted alert notification email body."""
    lines = [
        "🌿 Terprint Stock Alert",
        "=" * 40,
        f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]

    for match in alert_matches:
        alert = match["alert"]
        items = match["items"]
        lines.append(f"━━━ {alert['strain'].upper()} ━━━")
        if alert.get("dispensary"):
            lines.append(f"  Dispensary filter: {alert['dispensary']}")
        lines.append(f"  Found at {len(items)} location(s):")
        lines.append("")

        for item in items:
            disp = item.get("dispensary_name", item.get("dispensary", ""))
            store = item.get("store", {})
            city = store.get("city", "")
            store_name = store.get("store_name", store.get("store_id", ""))
            thc = item.get("cannabinoids", {}).get("thc_percent")
            price = item.get("pricing", {}).get("price")
            category = item.get("category", "")
            dist = item.get("distance_miles")

            location = f"{disp}"
            if store_name:
                location += f" — {store_name}"
            if city:
                location += f" ({city})"

            lines.append(f"  📍 {location}")
            details = []
            if category:
                details.append(category)
            if thc:
                details.append(f"THC: {thc}%")
            if price:
                details.append(f"${price:.2f}")
            if dist:
                details.append(f"{dist} mi away")
            if details:
                lines.append(f"     {' · '.join(details)}")
            lines.append("")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Manage your alerts: https://api.acidni.net/menus/api/stock/alerts",
        "",
        "This is an automated notification from Terprint.",
        "To unsubscribe, DELETE /api/stock/alerts/{alert_id}",
    ])

    return "\n".join(lines)


def _update_last_notified(alert_ids: list[str]) -> None:
    """Update last_notified timestamp for matched alerts."""
    alerts = _load_alerts()
    now_iso = datetime.now(timezone.utc).isoformat()
    changed = False
    for a in alerts:
        if a.get("id") in alert_ids:
            a["last_notified"] = now_iso
            changed = True
    if changed:
        _save_alerts(alerts)
