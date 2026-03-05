"""
Stock API Routes v2 for Menu Downloader

Provides real-time stock lookup endpoints with v2 nested schema.
Supports: search, geo-nearest, dispensary/store drill-down, summary,
genetics, strain alerts.

Copyright (c) 2026 Acidni LLC
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import stock indexer
try:
    from .stock_indexer import StockIndexer
    STOCK_INDEXER_AVAILABLE = True
except ImportError as e1:
    try:
        from stock_indexer import StockIndexer
        STOCK_INDEXER_AVAILABLE = True
    except ImportError as e2:
        STOCK_INDEXER_AVAILABLE = False
        logging.warning(f"StockIndexer import failed (relative): {e1}")
        logging.warning(f"StockIndexer import failed (direct): {e2}")
except Exception as e:
    STOCK_INDEXER_AVAILABLE = False
    logging.error(f"Unexpected error importing StockIndexer: {e}", exc_info=True)

# Import stock alerts
try:
    from .stock_alerts import create_alert, get_alerts_for_email, delete_alert
    STOCK_ALERTS_AVAILABLE = True
except ImportError:
    try:
        from stock_alerts import create_alert, get_alerts_for_email, delete_alert
        STOCK_ALERTS_AVAILABLE = True
    except ImportError:
        STOCK_ALERTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/stock", tags=["stock"])

# Global stock indexer instance
_stock_indexer: Optional["StockIndexer"] = None


def get_indexer() -> "StockIndexer":
    """Get or create stock indexer singleton."""
    global _stock_indexer
    if not STOCK_INDEXER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stock indexer not available")
    if _stock_indexer is None:
        _stock_indexer = StockIndexer()
    return _stock_indexer


def get_stock_index() -> dict:
    """Load current stock index from storage."""
    indexer = get_indexer()
    index = indexer.get_index()
    if index is None:
        raise HTTPException(
            status_code=503,
            detail="Stock index not available. Run POST /api/stock/build-index to create it.",
        )
    return index


# ===========================================================================
# Request/Response Models
# ===========================================================================

class BulkStockRequest(BaseModel):
    """Request model for bulk stock check."""
    batch_ids: List[str]


class AlertCreateRequest(BaseModel):
    """Request model for creating a strain alert."""
    email: str
    strain: str
    dispensary: Optional[str] = None
    max_distance_miles: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


# ===========================================================================
# Helper: Extract geo from v2 item
# ===========================================================================

def _item_lat(item: dict) -> Optional[float]:
    """Get latitude from a v2 stock item."""
    store = item.get("store")
    if isinstance(store, dict):
        return store.get("latitude")
    return item.get("latitude")  # fallback for legacy


def _item_lng(item: dict) -> Optional[float]:
    """Get longitude from a v2 stock item."""
    store = item.get("store")
    if isinstance(store, dict):
        return store.get("longitude")
    return item.get("longitude")


# ===========================================================================
# Endpoints
# ===========================================================================

@router.get("/status")
async def get_status():
    """Get Stock API status and index metadata."""
    try:
        index = get_stock_index()
        metadata = index.get("metadata", {})
        return {
            "status": "healthy",
            "service": "stock-api-v2",
            "index_available": True,
            "index_metadata": metadata,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException as e:
        return {
            "status": "degraded",
            "service": "stock-api-v2",
            "index_available": False,
            "error": e.detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/strains")
async def list_strains(
    q: Optional[str] = Query(None, description="Optional search filter"),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary"),
    limit: int = Query(200, description="Max results", le=1000),
):
    """List all available strain slugs (for autocomplete/browsing)."""
    index = get_stock_index()
    indexer = get_indexer()
    by_strain = index.get("by_strain", {})

    results = []
    for slug, items in sorted(by_strain.items()):
        if dispensary:
            items = [i for i in items if i.get("dispensary", "").lower() == dispensary.lower()]
            if not items:
                continue

        display_name = items[0].get("strain", slug) if items else slug
        dispensaries = sorted({i.get("dispensary", "") for i in items})
        categories = sorted({i.get("category", "") for i in items})

        entry = {
            "slug": slug,
            "name": display_name,
            "dispensaries": dispensaries,
            "categories": categories,
            "count": len(items),
        }

        if q:
            q_norm = indexer.normalize_strain_name(q)
            if q_norm not in slug and slug not in q_norm:
                # Word-level check
                q_words = set(q_norm.split("-"))
                slug_words = set(slug.split("-"))
                if not (q_words & slug_words):
                    continue

        results.append(entry)
        if len(results) >= limit:
            break

    return {"strains": results, "total": len(results)}


@router.get("/summary")
async def get_summary():
    """Get lightweight stock index summary for dashboards."""
    indexer = get_indexer()
    summary = indexer.get_summary()
    if summary is None:
        # Fall back to full index metadata
        index = get_stock_index()
        summary = index.get("summary", index.get("metadata", {}))
    return summary


@router.get("/search")
async def search_stock(
    strain: str = Query(..., description="Strain name to search for"),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary"),
    category: Optional[str] = Query(None, description="Filter by category"),
    lat: Optional[float] = Query(None, description="User latitude for distance sorting"),
    lng: Optional[float] = Query(None, description="User longitude for distance sorting"),
    max_distance: Optional[float] = Query(None, description="Max distance in miles", le=100),
    limit: int = Query(50, description="Max results to return", le=200),
):
    """Search for products by strain name with fuzzy/substring matching."""
    index = get_stock_index()
    indexer = get_indexer()

    strain_normalized = indexer.normalize_strain_name(strain)
    by_strain = index.get("by_strain", {})

    # 1. Try exact match first
    items = by_strain.get(strain_normalized, [])
    match_type = "exact"

    # 2. If no exact match, try substring matching (e.g. "cookie-crip" in "cookie-crip-whole-flower-35g")
    if not items:
        match_type = "substring"
        for slug, slug_items in by_strain.items():
            if strain_normalized in slug or slug in strain_normalized:
                items.extend(slug_items)

    # 3. If still nothing, try word-overlap matching (any word in the search appears in the slug)
    if not items:
        match_type = "fuzzy"
        search_words = set(strain_normalized.split("-"))
        for slug, slug_items in by_strain.items():
            slug_words = set(slug.split("-"))
            # Require at least 50% of search words to match
            overlap = search_words & slug_words
            if len(overlap) >= max(1, len(search_words) // 2):
                items.extend(slug_items)

    if not items:
        return {
            "strain": strain,
            "strain_normalized": strain_normalized,
            "match_type": "none",
            "matches": [],
            "total": 0,
            "message": f"No products found for strain '{strain}'",
            "suggestion": "Try a shorter or more common name",
        }

    filtered = list(items)

    if dispensary:
        filtered = [i for i in filtered if i.get("dispensary", "").lower() == dispensary.lower()]

    if category:
        filtered = [i for i in filtered if i.get("category", "").lower() == category.lower()]

    # Distance calculation
    if lat is not None and lng is not None:
        for item in filtered:
            item_lat = _item_lat(item)
            item_lng = _item_lng(item)
            if item_lat is not None and item_lng is not None:
                item["distance_miles"] = round(
                    indexer.calculate_distance(lat, lng, item_lat, item_lng), 2
                )

        if max_distance is not None:
            filtered = [
                i for i in filtered
                if i.get("distance_miles") is not None and i["distance_miles"] <= max_distance
            ]

        filtered.sort(
            key=lambda x: x.get("distance_miles") if x.get("distance_miles") is not None else float("inf")
        )

    filtered = filtered[:limit]

    return {
        "strain": strain,
        "strain_normalized": strain_normalized,
        "match_type": match_type,
        "matches": filtered,
        "total": len(filtered),
        "total_all_dispensaries": len(items),
        "user_location": {"lat": lat, "lng": lng} if lat is not None and lng is not None else None,
        "sorted_by_distance": bool(lat is not None and lng is not None),
    }


@router.get("/locations/{dispensary}")
async def get_dispensary_locations(
    dispensary: str,
    lat: Optional[float] = Query(None, description="User latitude for distance sorting"),
    lng: Optional[float] = Query(None, description="User longitude for distance sorting"),
):
    """Get all store locations for a dispensary."""
    indexer = get_indexer()
    dispensary_lower = dispensary.lower()
    locations = indexer.locations.get(dispensary_lower, {})

    if not locations:
        raise HTTPException(status_code=404, detail=f"No location data for dispensary '{dispensary}'")

    result = []
    for loc_id, loc_data in locations.items():
        info = {
            "location_id": loc_id,
            "dispensary": dispensary,
            "latitude": loc_data.get("lat"),
            "longitude": loc_data.get("lng"),
            "address": loc_data.get("address", ""),
            "distance_miles": None,
        }
        if lat is not None and lng is not None and loc_data.get("lat"):
            info["distance_miles"] = round(
                indexer.calculate_distance(lat, lng, loc_data["lat"], loc_data["lng"]), 2
            )
        result.append(info)

    if lat is not None and lng is not None:
        result.sort(key=lambda x: x["distance_miles"] if x["distance_miles"] is not None else float("inf"))

    return {
        "dispensary": dispensary,
        "locations": result,
        "total": len(result),
        "user_location": {"lat": lat, "lng": lng} if lat is not None and lng is not None else None,
        "sorted_by_distance": bool(lat is not None and lng is not None),
    }


@router.get("/nearest")
async def get_nearest_stock(
    strain: str = Query(..., description="Strain name to search for"),
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    max_distance: float = Query(50, description="Max distance in miles", le=100),
    limit: int = Query(10, description="Max results to return", le=50),
):
    """Find nearest dispensaries carrying a specific strain."""
    index = get_stock_index()
    indexer = get_indexer()

    strain_normalized = indexer.normalize_strain_name(strain)
    by_strain = index.get("by_strain", {})

    # Exact match first, then substring
    items = by_strain.get(strain_normalized, [])
    if not items:
        for slug, slug_items in by_strain.items():
            if strain_normalized in slug or slug in strain_normalized:
                items.extend(slug_items)

    if not items:
        return {
            "strain": strain,
            "user_location": {"lat": lat, "lng": lng},
            "max_distance_miles": max_distance,
            "nearest_locations": [],
            "total_found": 0,
            "message": f"No products found for strain '{strain}'",
        }

    with_location = [i for i in items if _item_lat(i) is not None and _item_lng(i) is not None]

    for item in with_location:
        item["distance_miles"] = round(
            indexer.calculate_distance(lat, lng, _item_lat(item), _item_lng(item)), 2
        )

    nearby = [i for i in with_location if i["distance_miles"] <= max_distance]
    nearby.sort(key=lambda x: x["distance_miles"])

    return {
        "strain": strain,
        "strain_normalized": strain_normalized,
        "user_location": {"lat": lat, "lng": lng},
        "max_distance_miles": max_distance,
        "nearest_locations": nearby[:limit],
        "total_found": len(nearby),
        "total_within_radius": len(nearby),
    }


# ===========================================================================
# Alert Endpoints — Strain Watchlist
# ===========================================================================

@router.post("/alerts")
async def create_strain_alert(request: AlertCreateRequest):
    """Subscribe to email alerts when a strain comes in stock."""
    if not STOCK_ALERTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Alert service not available")

    indexer = get_indexer()
    strain_slug = indexer.normalize_strain_name(request.strain)

    alert = create_alert(
        email=request.email,
        strain=request.strain,
        strain_slug=strain_slug,
        dispensary=request.dispensary,
        max_distance_miles=request.max_distance_miles,
        lat=request.lat,
        lng=request.lng,
    )

    is_dup = alert.pop("_duplicate", False)
    return {
        "success": True,
        "alert": alert,
        "message": "Alert already exists" if is_dup else f"Alert created — you'll be emailed when '{request.strain}' is in stock",
    }


@router.get("/alerts/{email}")
async def get_user_alerts(email: str):
    """Get all active alerts for an email address."""
    if not STOCK_ALERTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Alert service not available")

    alerts = get_alerts_for_email(email)
    return {
        "email": email,
        "alerts": alerts,
        "total": len(alerts),
    }


@router.delete("/alerts/{alert_id}")
async def remove_alert(alert_id: str):
    """Deactivate a strain alert."""
    if not STOCK_ALERTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Alert service not available")

    success = delete_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"success": True, "message": f"Alert {alert_id} deactivated"}


# ===========================================================================
# Catch-all dispensary routes (MUST be last - matches any path segment)
# ===========================================================================

@router.get("/{dispensary}")
async def get_dispensary_stock(
    dispensary: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, description="Max results to return", le=500),
):
    """Get all stock for a specific dispensary."""
    index = get_stock_index()

    dispensary_lower = dispensary.lower()
    dispensary_items = index.get("by_dispensary", {}).get(dispensary_lower, [])

    if not dispensary_items:
        return {
            "dispensary": dispensary,
            "found": False,
            "total": 0,
            "items": [],
            "message": f"No inventory found for dispensary '{dispensary}'",
        }

    filtered = dispensary_items
    if category:
        filtered = [i for i in filtered if i.get("category", "").lower() == category.lower()]

    return {
        "dispensary": dispensary,
        "found": True,
        "total": len(filtered[:limit]),
        "total_unfiltered": len(dispensary_items),
        "items": filtered[:limit],
    }


@router.get("/{dispensary}/{batch_id}")
async def get_batch_stock(dispensary: str, batch_id: str):
    """Get stock information for a specific batch at a dispensary."""
    index = get_stock_index()

    dispensary_items = index.get("by_dispensary", {}).get(dispensary.lower(), [])

    for item in dispensary_items:
        if item.get("batch_id") == batch_id:
            return {"found": True, "batch": item, "dispensary": dispensary, "batch_id": batch_id}

    raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found at {dispensary}")


@router.post("/build-index")
async def build_stock_index():
    """Rebuild the stock index from menu files + SQL enrichment."""
    logger.info("POST /build-index triggered")
    try:
        indexer = get_indexer()
        index = indexer.build_index()
        path = indexer.save_index(index)

        metadata = index.get("metadata", {})
        return {
            "success": True,
            "index_path": path,
            "metadata": metadata,
            "message": (
                f"Stock index v2 built: {metadata.get('total_items', 0)} items, "
                f"{metadata.get('unique_strains', 0)} strains"
            ),
        }
    except Exception as e:
        logger.error(f"Failed to build stock index: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to build stock index: {e}")


@router.post("/run")
async def manual_menu_download():
    """Trigger manual menu download (alias)."""
    return {"message": "Use POST /run endpoint for manual downloads", "redirect": "/run"}


@router.post("/match-batches")
async def match_batches():
    """Match batches to current inventory (not yet implemented)."""
    raise HTTPException(status_code=501, detail="Batch matching not yet implemented")


@router.post("/bulk-check")
async def bulk_stock_check(request: BulkStockRequest):
    """Check stock for multiple batches at once."""
    index = get_stock_index()

    if not request.batch_ids:
        raise HTTPException(status_code=400, detail="batch_ids array cannot be empty")

    results = []
    for batch_id in request.batch_ids:
        found_item = None
        for dispensary_items in index.get("by_dispensary", {}).values():
            for item in dispensary_items:
                if item.get("batch_id") == batch_id:
                    found_item = item
                    break
            if found_item:
                break

        results.append({
            "batch_id": batch_id,
            "found": found_item is not None,
            "dispensary": found_item.get("dispensary") if found_item else None,
            "item": found_item,
        })

    return {
        "requested": len(request.batch_ids),
        "found": sum(1 for r in results if r["found"]),
        "not_found": sum(1 for r in results if not r["found"]),
        "results": results,
    }
