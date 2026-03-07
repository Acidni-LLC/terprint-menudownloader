"""
Stock API Routes v2 for Menu Downloader

Provides real-time stock lookup endpoints with v2 nested schema.
Supports: search, geo-nearest, dispensary/store drill-down, summary,
genetics, strain alerts.

Copyright (c) 2026 Acidni LLC
"""
import logging
import os
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

# Import stock availability tracker
try:
    from .stock_indexer import StockAvailabilityTracker
    AVAILABILITY_TRACKER_AVAILABLE = True
except ImportError:
    try:
        from stock_indexer import StockAvailabilityTracker
        AVAILABILITY_TRACKER_AVAILABLE = True
    except ImportError:
        AVAILABILITY_TRACKER_AVAILABLE = False

# Import stock ledger writer
try:
    from .stock_indexer import StockLedgerWriter
    STOCK_LEDGER_AVAILABLE = True
except ImportError:
    try:
        from stock_indexer import StockLedgerWriter
        STOCK_LEDGER_AVAILABLE = True
    except ImportError:
        STOCK_LEDGER_AVAILABLE = False

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
    has_terpenes: Optional[bool] = Query(None, description="Filter by terpene data availability (true=with terpenes, false=without)"),
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

    if has_terpenes is not None:
        if has_terpenes:
            filtered = [i for i in filtered if i.get("terpenes", {}).get("profile")]
        else:
            filtered = [i for i in filtered if not i.get("terpenes", {}).get("profile")]

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


# ===========================================================================
# Browse Endpoint — Server-Side Filtering for Table Views
# ===========================================================================

@router.get("/browse")
async def browse_stock(
    # Filters
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug (e.g., 'trulieve')"),
    store: Optional[str] = Query(None, description="Filter by store name or ID"),
    strain: Optional[str] = Query(None, description="Filter by strain name (supports partial match)"),
    strains: Optional[str] = Query(None, description="Comma-separated list of exact strain names to filter (for favorites)"),
    product_type: Optional[str] = Query(None, description="Filter by category (Flower, Concentrates, etc.)"),
    product_sub_type: Optional[str] = Query(None, description="Filter by subcategory if applicable"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    in_stock_hours: Optional[float] = Query(None, description="Only items in stock within N hours"),
    has_terpenes: Optional[bool] = Query(None, description="Filter by terpene data availability. True=only with terpenes, False=only without, None=all"),
    # Sorting
    sort_by: str = Query("time_in_stock", description="Sort field: time_in_stock, price, product_name, dispensary, store"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
    # Pagination
    limit: int = Query(50, description="Max results per page", le=500),
    offset: int = Query(0, description="Offset for pagination"),
):
    """
    Browse all stock items with server-side filtering, sorting, and pagination.
    
    Returns a flat schema optimized for table display with deep links to:
    - Product page at dispensary
    - Strain detail in Terprint AI Teams
    - Batch detail in Terprint AI Teams  
    - Terprint Portal strain page
    - Terprint Web strain page
    """
    index = get_stock_index()
    indexer = get_indexer()
    
    # Get all items from all dispensaries
    all_items: List[dict] = []
    by_dispensary = index.get("by_dispensary", {})
    for disp_items in by_dispensary.values():
        all_items.extend(disp_items)
    
    # If no by_dispensary, fall back to by_strain
    if not all_items:
        by_strain = index.get("by_strain", {})
        for strain_items in by_strain.values():
            all_items.extend(strain_items)
    
    # Apply filters
    filtered = all_items
    
    if dispensary:
        filtered = [i for i in filtered if i.get("dispensary", "").lower() == dispensary.lower()]
    
    if store:
        store_lower = store.lower()
        filtered = [
            i for i in filtered 
            if store_lower in (i.get("store", {}).get("store_name", "") or "").lower()
            or store_lower in (i.get("store", {}).get("store_id", "") or "").lower()
            or store_lower in (i.get("store", {}).get("city", "") or "").lower()
        ]
    
    if strain:
        strain_norm = indexer.normalize_strain_name(strain)
        filtered = [
            i for i in filtered
            if strain_norm in i.get("strain_slug", "")
            or strain_norm in indexer.normalize_strain_name(i.get("strain", ""))
            or strain.lower() in (i.get("product_name", "") or "").lower()
        ]
    
    # Favorites filter: exact match against comma-separated strain names
    if strains:
        strain_list = [s.strip().lower() for s in strains.split(",") if s.strip()]
        if strain_list:
            # Build normalized set for O(1) lookup
            strain_set = set(strain_list)
            strain_slug_set = {indexer.normalize_strain_name(s) for s in strain_list}
            filtered = [
                i for i in filtered
                if (i.get("strain", "") or "").lower() in strain_set
                or i.get("strain_slug", "") in strain_slug_set
            ]
    
    if product_type:
        filtered = [i for i in filtered if i.get("category", "").lower() == product_type.lower()]
    
    if product_sub_type:
        # Check in product_name for sub-type keywords
        sub_lower = product_sub_type.lower()
        filtered = [
            i for i in filtered
            if sub_lower in (i.get("product_name", "") or "").lower()
            or sub_lower in (i.get("category", "") or "").lower()
        ]
    
    if min_price is not None:
        filtered = [
            i for i in filtered
            if (i.get("pricing", {}).get("price") or 0) >= min_price
        ]
    
    if max_price is not None:
        filtered = [
            i for i in filtered
            if (i.get("pricing", {}).get("price") or float("inf")) <= max_price
        ]
    
    if in_stock_hours is not None:
        filtered = [
            i for i in filtered
            if (i.get("availability", {}).get("freshness_hours") or float("inf")) <= in_stock_hours
        ]
    
    if has_terpenes is not None:
        if has_terpenes:
            filtered = [i for i in filtered if (i.get("terpenes", {}) or {}).get("profile")]
        else:
            filtered = [i for i in filtered if not (i.get("terpenes", {}) or {}).get("profile")]
    
    total_filtered = len(filtered)
    
    # Sort
    def get_sort_key(item: dict):
        if sort_by == "price":
            return item.get("pricing", {}).get("price") or 0
        elif sort_by == "product_name":
            return (item.get("product_name") or "").lower()
        elif sort_by == "dispensary":
            return (item.get("dispensary_name") or item.get("dispensary") or "").lower()
        elif sort_by == "store":
            return (item.get("store", {}).get("store_name") or "").lower()
        elif sort_by == "strain":
            return (item.get("strain") or "").lower()
        else:  # time_in_stock
            return item.get("availability", {}).get("freshness_hours") or float("inf")
    
    reverse_sort = sort_order.lower() == "desc"
    filtered.sort(key=get_sort_key, reverse=reverse_sort)
    
    # Paginate
    paginated = filtered[offset:offset + limit]
    
    # Transform to flat table schema with deep links
    def to_table_row(item: dict) -> dict:
        pricing = item.get("pricing", {}) or {}
        availability = item.get("availability", {}) or {}
        store_info = item.get("store", {}) or {}
        links = item.get("links", {}) or {}
        terpenes = item.get("terpenes", {}) or {}
        terpene_profile = terpenes.get("profile", {}) or {}
        terpene_top3 = terpenes.get("top_3", []) or []
        
        strain_slug = item.get("strain_slug", "")
        batch_id = item.get("batch_id", "")
        disp = item.get("dispensary", "")
        
        # Build deep links
        # Teams app links (relative paths for the tab)
        teams_strain_url = f"/strain/{strain_slug}" if strain_slug else None
        teams_batch_url = f"/batch/{batch_id}" if batch_id else None
        
        # Terprint Web links
        web_base = "https://terprint.acidni.net"
        web_strain_url = f"{web_base}/strains/{strain_slug}" if strain_slug else None
        web_batch_url = f"{web_base}/batches/{batch_id}" if batch_id else None
        
        # Terprint Portal links
        portal_base = "https://ca-terprint-portal.greenbay-731aa80e.eastus2.azurecontainerapps.io"
        portal_strain_url = f"{portal_base}/stock?strain={strain_slug}" if strain_slug else None
        
        # Extract weight from product name or pricing
        weight_grams = pricing.get("weight_grams")
        size_uom = f"{weight_grams}g" if weight_grams else _extract_size_from_name(item.get("product_name", ""))
        
        return {
            "id": item.get("id", ""),
            "dispensary": item.get("dispensary_name") or item.get("dispensary", ""),
            "dispensary_slug": disp,
            "store": store_info.get("store_name") or store_info.get("city") or "",
            "store_city": store_info.get("city", ""),
            "product_name": item.get("product_name", ""),
            "strain": item.get("strain", ""),
            "strain_slug": strain_slug,
            "product_type": item.get("category", ""),
            "product_sub_type": _extract_sub_type(item.get("product_name", ""), item.get("category", "")),
            "size_uom": size_uom,
            "price": pricing.get("price"),
            "price_per_gram": pricing.get("price_per_gram"),
            "time_in_stock_hours": availability.get("freshness_hours"),
            "last_seen": availability.get("last_seen", ""),
            "batch_id": batch_id,
            "batch_name": item.get("product_name", "") or "",
            # Deep links
            "product_url": links.get("product_url") or links.get("url"),
            "teams_strain_url": teams_strain_url,
            "teams_batch_url": teams_batch_url,
            "web_strain_url": web_strain_url,
            "web_batch_url": web_batch_url,
            "portal_strain_url": portal_strain_url,
            # Terpene data
            "has_terpenes": bool(terpene_profile),
            "top_terpenes": [
                {"name": t, "percentage": terpene_profile.get(t)}
                for t in terpene_top3
            ] if terpene_top3 else [],
            # Store location for map view
            "store_lat": store_info.get("latitude"),
            "store_lng": store_info.get("longitude"),
            "store_address": store_info.get("address", ""),
        }
    
    rows = [to_table_row(item) for item in paginated]
    
    # Get filter options (unique values for dropdowns)
    all_dispensaries = sorted({i.get("dispensary_name") or i.get("dispensary", "") for i in all_items if i.get("dispensary")})
    all_categories = sorted({i.get("category", "") for i in all_items if i.get("category")})
    all_stores = sorted({i.get("store", {}).get("store_name", "") for i in all_items if i.get("store", {}).get("store_name")})
    
    return {
        "items": rows,
        "total": total_filtered,
        "total_all": len(all_items),
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_filtered,
        "filters_applied": {
            "dispensary": dispensary,
            "store": store,
            "strain": strain,
            "strains": strains,
            "product_type": product_type,
            "product_sub_type": product_sub_type,
            "min_price": min_price,
            "max_price": max_price,
            "in_stock_hours": in_stock_hours,
            "has_terpenes": has_terpenes,
        },
        "sort": {"by": sort_by, "order": sort_order},
        "filter_options": {
            "dispensaries": all_dispensaries,
            "categories": all_categories,
            "stores": all_stores[:50],  # Limit store list
        },
    }


def _extract_size_from_name(product_name: str) -> str:
    """Extract size/weight from product name."""
    if not product_name:
        return ""
    # Common patterns: "3.5g", "1/8", "1oz", "28g", etc.
    import re
    patterns = [
        r'(\d+\.?\d*)\s*g\b',  # 3.5g, 28g
        r'(\d+\.?\d*)\s*oz\b',  # 1oz
        r'(1/8|1/4|1/2)\b',  # fractions
        r'(\d+)\s*pack\b',  # pack count
        r'(\d+)\s*ct\b',  # count
    ]
    for pattern in patterns:
        match = re.search(pattern, product_name, re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _extract_sub_type(product_name: str, category: str) -> str:
    """Extract sub-type from product name."""
    if not product_name:
        return ""
    name_lower = product_name.lower()
    
    # Common sub-types by category
    sub_types = {
        "flower": ["whole flower", "ground", "minis", "smalls", "shake", "pre-roll", "pre-ground", "popcorn"],
        "concentrates": ["live rosin", "live resin", "shatter", "wax", "budder", "crumble", "diamonds", "sauce", "badder", "batter", "hash", "rosin", "distillate"],
        "vapes": ["cart", "cartridge", "disposable", "pod", "510"],
        "edibles": ["gummies", "chocolate", "candy", "capsule", "tincture", "rso"],
    }
    
    cat_lower = category.lower() if category else ""
    
    # Check category-specific sub-types first
    for cat, types in sub_types.items():
        if cat in cat_lower or cat in name_lower:
            for sub in types:
                if sub in name_lower:
                    return sub.title()
    
    # General search
    for types in sub_types.values():
        for sub in types:
            if sub in name_lower:
                return sub.title()
    
    return ""


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
# Availability History & Hot Products Endpoints
# ===========================================================================

def _get_tracker() -> "StockAvailabilityTracker":
    """Get a StockAvailabilityTracker instance using the stock indexer's blob container."""
    if not AVAILABILITY_TRACKER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Availability tracker not available")
    indexer = get_indexer()
    container = indexer._get_blob_container()
    if not container:
        raise HTTPException(status_code=503, detail="Blob storage not available")
    return StockAvailabilityTracker(container, indexer.INDEX_PREFIX)


@router.get("/hot-products")
async def get_hot_products(
    limit: int = Query(20, description="Max results per category", le=100),
    category: Optional[str] = Query(None, description="Filter by product category"),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
):
    """
    Get trending/hot products — fast sellers, frequently restocked items.

    Hotness score formula:
        (restock_count * 30) + (1/avg_days_in_stock * 40) + recency_bonus(20)

    Higher score = hotter product (sells out fast, restocks often).
    """
    tracker = _get_tracker()
    analytics = tracker.get_hot_products()
    if not analytics:
        raise HTTPException(
            status_code=503,
            detail="Hot products data not yet available. Run POST /api/stock/build-index first.",
        )

    def _filter(items: list) -> list:
        filtered = items
        if category:
            filtered = [i for i in filtered if i.get("category", "").lower() == category.lower()]
        if dispensary:
            filtered = [i for i in filtered if i.get("dispensary", "").lower() == dispensary.lower()]
        return filtered[:limit]

    return {
        "updated_at": analytics.get("updated_at"),
        "fastest_sellers": _filter(analytics.get("fastest_sellers", [])),
        "new_arrivals": _filter(analytics.get("new_arrivals", [])),
        "long_stayers": _filter(analytics.get("long_stayers", [])),
        "recently_sold_out": _filter(analytics.get("recently_sold_out", [])),
        "strain_store_counts": analytics.get("strain_store_counts", {}),
    }


@router.get("/new-arrivals")
async def get_new_arrivals(
    hours: int = Query(72, description="Show items first seen within this many hours", le=168),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
    category: Optional[str] = Query(None, description="Filter by product category"),
    limit: int = Query(50, description="Max results", le=200),
):
    """
    Get products that appeared for the first time recently.

    These are brand-new drops — products that were never seen before
    in the stock index, or that appeared for the first time at a store.
    """
    tracker = _get_tracker()
    analytics = tracker.get_hot_products()
    if not analytics:
        raise HTTPException(
            status_code=503,
            detail="New arrivals data not yet available. Run POST /api/stock/build-index first.",
        )

    arrivals = analytics.get("new_arrivals", [])

    # Filter by hours threshold
    arrivals = [a for a in arrivals if a.get("hours_ago", 999) <= hours]

    if dispensary:
        arrivals = [a for a in arrivals if a.get("dispensary", "").lower() == dispensary.lower()]
    if category:
        arrivals = [a for a in arrivals if a.get("category", "").lower() == category.lower()]

    arrivals = arrivals[:limit]

    return {
        "updated_at": analytics.get("updated_at"),
        "hours_window": hours,
        "new_arrivals": arrivals,
        "total": len(arrivals),
    }


@router.get("/recently-sold-out")
async def get_recently_sold_out(
    hours: int = Query(48, description="Show items sold out within this many hours", le=168),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
    category: Optional[str] = Query(None, description="Filter by product category"),
    limit: int = Query(50, description="Max results", le=200),
):
    """
    Get products that recently went out of stock.

    Useful for identifying high-demand products and setting restock alerts.
    Shows how long the product was available before selling out.
    """
    tracker = _get_tracker()
    analytics = tracker.get_hot_products()
    if not analytics:
        raise HTTPException(
            status_code=503,
            detail="Sold-out data not yet available. Run POST /api/stock/build-index first.",
        )

    sold_out = analytics.get("recently_sold_out", [])

    sold_out = [s for s in sold_out if s.get("hours_since_sold_out", 999) <= hours]

    if dispensary:
        sold_out = [s for s in sold_out if s.get("dispensary", "").lower() == dispensary.lower()]
    if category:
        sold_out = [s for s in sold_out if s.get("category", "").lower() == category.lower()]

    sold_out = sold_out[:limit]

    return {
        "updated_at": analytics.get("updated_at"),
        "hours_window": hours,
        "recently_sold_out": sold_out,
        "total": len(sold_out),
    }


@router.get("/availability-history/{strain_slug}")
async def get_strain_availability_history(
    strain_slug: str,
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
):
    """
    Get full availability lifecycle history for a specific strain.

    Shows when the strain appeared at each store, how long it stayed,
    restock events, and current status. Useful for predicting restock
    patterns and understanding product velocity.
    """
    tracker = _get_tracker()
    history = tracker.get_history()
    if not history:
        raise HTTPException(
            status_code=503,
            detail="Availability history not yet available. Run POST /api/stock/build-index first.",
        )

    items = history.get("items", {})
    indexer = get_indexer()
    target_slug = indexer.normalize_strain_name(strain_slug)

    matching = []
    for key, entry in items.items():
        entry_slug = entry.get("strain_slug", "")
        if entry_slug == target_slug or target_slug in entry_slug:
            if dispensary and entry.get("dispensary", "").lower() != dispensary.lower():
                continue
            matching.append({
                "key": key,
                **entry,
            })

    if not matching:
        return {
            "strain_slug": target_slug,
            "found": False,
            "entries": [],
            "total": 0,
            "message": f"No availability history for strain '{strain_slug}'",
        }

    # Summary stats
    in_stock_entries = [e for e in matching if e.get("in_stock")]
    out_of_stock_entries = [e for e in matching if not e.get("in_stock")]
    total_restocks = sum(e.get("times_restocked", 0) for e in matching)
    days_values = [e["days_in_stock"] for e in matching if e.get("days_in_stock") is not None]
    avg_days = round(sum(days_values) / len(days_values), 1) if days_values else None

    dispensaries_available = sorted({e.get("dispensary", "") for e in in_stock_entries})
    stores_available = sorted({e.get("store_name", "") for e in in_stock_entries if e.get("store_name")})

    return {
        "strain_slug": target_slug,
        "strain": matching[0].get("strain", target_slug) if matching else target_slug,
        "found": True,
        "summary": {
            "currently_in_stock": len(in_stock_entries),
            "out_of_stock": len(out_of_stock_entries),
            "total_restocks": total_restocks,
            "avg_days_in_stock": avg_days,
            "dispensaries_available": dispensaries_available,
            "stores_available": stores_available,
        },
        "entries": matching,
        "total": len(matching),
        "tracking_since": history.get("tracking_since"),
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
# Terpene Data Status — batches missing terpene profiles
# ===========================================================================

@router.get("/batches/no-terpenes")
async def get_batches_without_terpenes(
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
    status: Optional[str] = Query(None, description="Filter by terpene_data_status: pending, unavailable, retry"),
    limit: int = Query(100, description="Max results", le=500),
):
    """List batches that have no terpene data — for retry scheduling and monitoring.

    Returns batches from SQL where terpene_data_status is NOT 'available'.
    Useful for identifying products that need re-scraping or COA lookup.
    """
    try:
        import pymssql

        conn = pymssql.connect(
            server="acidni-sql.database.windows.net",
            user="adm",
            password=os.environ.get("SQL_PASSWORD", ""),
            database="terprint",
            tds_version="7.3",
        )
        cursor = conn.cursor(as_dict=True)

        where_clauses = ["b.terpene_data_status != 'available'"]
        params: list = []

        if dispensary:
            where_clauses.append("LOWER(g.Name) = %s")
            params.append(dispensary.lower())

        if status:
            where_clauses.append("b.terpene_data_status = %s")
            params.append(status)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(
            f"""SELECT TOP {int(limit)}
                    b.BatchId, b.Name, b.Date, b.StoreName,
                    b.totalTerpenes, b.totalCannabinoids,
                    b.terpene_data_status, b.terpene_attempts, b.terpene_retry_after,
                    b.ProductType, b.StrainClassification,
                    g.Name AS Dispensary,
                    s.Name AS StrainName
                FROM Batch b
                LEFT JOIN Grower g ON b.GrowerID = g.GrowerID
                LEFT JOIN Strain s ON b.StrainID = s.StrainID
                WHERE {where_sql}
                ORDER BY b.terpene_data_status, b.created DESC""",
            tuple(params),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Serialise datetimes
        for row in rows:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()

        return {
            "batches": rows,
            "total": len(rows),
            "filters": {"dispensary": dispensary, "status": status},
        }

    except Exception as e:
        logger.error(f"Failed to query batches without terpenes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

        # Availability tracker stats (populated by save_index)
        tracker_info = {}
        if AVAILABILITY_TRACKER_AVAILABLE:
            try:
                tracker = _get_tracker()
                hot = tracker.get_hot_products()
                if hot:
                    tracker_info = {
                        "new_arrivals": len(hot.get("new_arrivals", [])),
                        "fastest_sellers": len(hot.get("fastest_sellers", [])),
                        "recently_sold_out": len(hot.get("recently_sold_out", [])),
                        "long_stayers": len(hot.get("long_stayers", [])),
                    }
            except Exception:
                pass

        return {
            "success": True,
            "index_path": path,
            "metadata": metadata,
            "availability_tracking": tracker_info,
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


# =============================================================================
# Stock Ledger Routes — Persistent History (Cosmos DB)
# =============================================================================

def _get_ledger() -> "StockLedgerWriter":
    """Get a StockLedgerWriter instance."""
    if not STOCK_LEDGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stock ledger not available")
    return StockLedgerWriter()


@router.get("/ledger/strain/{strain_slug}")
async def get_strain_ledger(
    strain_slug: str,
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    event: Optional[str] = Query(None, description="Filter by event type: appeared, disappeared, restocked"),
    limit: int = Query(100, description="Max results", le=500),
):
    """
    Get the full persistent event history for a specific strain.

    Unlike /availability-history which only keeps 90 days and 50 events,
    this endpoint returns ALL recorded stock events from the permanent
    Cosmos DB ledger — every time the strain appeared, disappeared, or
    was restocked at any store.

    Use this to answer: "When was Blue Dream last in stock at Trulieve Tampa?"
    """
    ledger = _get_ledger()
    indexer = get_indexer()
    normalized_slug = indexer.normalize_strain_name(strain_slug)

    events = ledger.query_strain_history(
        strain_slug=normalized_slug,
        dispensary=dispensary,
        store_id=store_id,
        event_type=event,
        limit=limit,
    )

    return {
        "strain_slug": normalized_slug,
        "total_events": len(events),
        "filters": {
            "dispensary": dispensary,
            "store_id": store_id,
            "event": event,
        },
        "events": events,
    }


@router.get("/ledger/strain/{strain_slug}/timeline")
async def get_strain_timeline(
    strain_slug: str,
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Get a condensed timeline of in-stock/out-of-stock periods for a strain.

    Shows when the strain was available at each store, how long it stayed,
    and the price/THC at each appearance. Useful for visualizing
    availability patterns over time.
    """
    ledger = _get_ledger()
    indexer = get_indexer()
    normalized_slug = indexer.normalize_strain_name(strain_slug)

    timeline = ledger.get_strain_timeline(
        strain_slug=normalized_slug,
        dispensary=dispensary,
        store_id=store_id,
    )

    # Compute summary stats
    total_periods = len(timeline)
    currently_in_stock = sum(1 for p in timeline if p.get("out_of_stock_at") is None)
    avg_days = None
    completed_periods = [p for p in timeline if p.get("days_available") is not None]
    if completed_periods:
        avg_days = round(
            sum(p["days_available"] for p in completed_periods) / len(completed_periods),
            1,
        )

    return {
        "strain_slug": normalized_slug,
        "total_periods": total_periods,
        "currently_in_stock": currently_in_stock,
        "avg_days_available": avg_days,
        "timeline": timeline,
    }


@router.get("/ledger/store/{store_id}")
async def get_store_ledger(
    store_id: str,
    event: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, description="Max results", le=500),
):
    """
    Get all stock events at a specific store.

    Shows what products have appeared, disappeared, and been restocked
    at a particular dispensary location. Useful for understanding what
    your local store has carried over time.
    """
    ledger = _get_ledger()

    events = ledger.query_store_history(
        store_id=store_id,
        event_type=event,
        limit=limit,
    )

    return {
        "store_id": store_id,
        "total_events": len(events),
        "events": events,
    }


@router.get("/ledger/recent")
async def get_recent_ledger_events(
    event: Optional[str] = Query(None, description="Filter: appeared, disappeared, restocked"),
    hours: int = Query(72, description="Look back this many hours", le=168),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary slug"),
    limit: int = Query(100, description="Max results", le=500),
):
    """
    Get recent stock events across all strains.

    Shows the latest stock movements — new drops, sold-out items,
    and restocks — across the entire platform.
    """
    ledger = _get_ledger()

    events = ledger.query_recent_events(
        event_type=event,
        hours=hours,
        dispensary=dispensary,
        limit=limit,
    )

    return {
        "hours_window": hours,
        "total_events": len(events),
        "filters": {
            "event": event,
            "dispensary": dispensary,
        },
        "events": events,
    }


@router.get("/ledger/stats")
async def get_ledger_stats():
    """
    Get aggregate statistics from the persistent stock ledger.

    Shows total events recorded, breakdown by type, and count of
    unique strains tracked over the lifetime of the ledger.
    """
    ledger = _get_ledger()
    stats = ledger.get_ledger_stats()

    if not stats or "error" in stats:
        raise HTTPException(
            status_code=503,
            detail=f"Ledger stats unavailable: {stats.get('error', 'unknown')}",
        )

    return stats
