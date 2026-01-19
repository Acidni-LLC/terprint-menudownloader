"""
Stock API Routes for Menu Downloader

Provides real-time stock lookup endpoints integrated into Menu Downloader.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import stock indexer from terprint-core
try:
    from stock_indexer import StockIndexer
    STOCK_INDEXER_AVAILABLE = True
except ImportError:
    STOCK_INDEXER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/stock", tags=["stock"])

# Global stock indexer instance
_stock_indexer: Optional['StockIndexer'] = None


def get_indexer() -> 'StockIndexer':
    """Get or create stock indexer instance."""
    global _stock_indexer
    if not STOCK_INDEXER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Stock indexer not available - terprint-core package required"
        )
    
    if _stock_indexer is None:
        _stock_indexer = StockIndexer()
    return _stock_indexer


def get_stock_index():
    """Load current stock index from storage."""
    indexer = get_indexer()
    index = indexer.get_index()
    
    if index is None:
        raise HTTPException(
            status_code=503,
            detail="Stock index not available. Run POST /api/stock/build-index to create it."
        )
    
    return index


# =============================================================================
# Request/Response Models
# =============================================================================

class BulkStockRequest(BaseModel):
    """Request model for bulk stock check."""
    batch_ids: List[str]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status")
async def get_status():
    """Get Stock API status and index metadata."""
    try:
        index = get_stock_index()
        metadata = index["metadata"]
        
        return {
            "status": "healthy",
            "service": "stock-api",
            "index_available": True,
            "index_metadata": metadata,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException as e:
        return {
            "status": "degraded",
            "service": "stock-api",
            "index_available": False,
            "error": e.detail,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/search")
async def search_stock(
    strain: str = Query(..., description="Strain name to search for"),
    dispensary: Optional[str] = Query(None, description="Filter by dispensary"),
    category: Optional[str] = Query(None, description="Filter by category"),
    lat: Optional[float] = Query(None, description="User latitude for distance sorting"),
    lng: Optional[float] = Query(None, description="User longitude for distance sorting"),
    max_distance: Optional[float] = Query(None, description="Max distance in miles", le=100),
    limit: int = Query(50, description="Max results to return", le=200)
):
    """Search for products by strain name, optionally filtered by location."""
    index = get_stock_index()
    indexer = get_indexer()
    
    # Normalize strain name for lookup
    strain_normalized = indexer.normalize_strain_name(strain)
    
    # Get all items for this strain
    items = index["by_strain"].get(strain_normalized, [])
    
    if not items:
        return {
            "strain": strain,
            "strain_normalized": strain_normalized,
            "matches": [],
            "total": 0,
            "message": f"No products found for strain '{strain}'"
        }
    
    # Apply filters
    filtered = items
    
    if dispensary:
        filtered = [item for item in filtered if item["dispensary"].lower() == dispensary.lower()]
    
    if category:
        filtered = [item for item in filtered if item["category"].lower() == category.lower()]
    
    # Calculate distances if user location provided
    if lat and lng:
        indexer = get_indexer()
        for item in filtered:
            if item.get('latitude') and item.get('longitude'):
                item['distance_miles'] = round(indexer.calculate_distance(
                    lat, lng, item['latitude'], item['longitude']
                ), 2)
        
        # Filter by max distance
        if max_distance:
            filtered = [
                item for item in filtered 
                if item.get('distance_miles') is not None and item['distance_miles'] <= max_distance
            ]
        
        # Sort by distance (nearest first)
        filtered.sort(key=lambda x: x.get('distance_miles') if x.get('distance_miles') is not None else float('inf'))
    
    # Limit results
    filtered = filtered[:limit]
    
    return {
        "strain": strain,
        "strain_normalized": strain_normalized,
        "matches": filtered,
        "total": len(filtered),
        "total_all_dispensaries": len(items),
        "user_location": {"lat": lat, "lng": lng} if lat and lng else None,
        "sorted_by_distance": bool(lat and lng)
    }


@router.get("/locations/{dispensary}")
async def get_dispensary_locations(
    dispensary: str,
    lat: Optional[float] = Query(None, description="User latitude for distance sorting"),
    lng: Optional[float] = Query(None, description="User longitude for distance sorting")
):
    """Get all store locations for a dispensary."""
    indexer = get_indexer()
    dispensary_lower = dispensary.lower()
    
    locations = indexer.locations.get(dispensary_lower, {})
    
    if not locations:
        raise HTTPException(
            status_code=404,
            detail=f"No location data found for dispensary '{dispensary}'"
        )
    
    result = []
    for location_id, location_data in locations.items():
        location_info = {
            "location_id": location_id,
            "dispensary": dispensary,
            "latitude": location_data['lat'],
            "longitude": location_data['lng'],
            "address": location_data['address'],
            "distance_miles": None
        }
        
        # Calculate distance if user location provided
        if lat is not None and lng is not None and location_data.get('lat'):
            location_info['distance_miles'] = round(indexer.calculate_distance(
                lat, lng, location_data['lat'], location_data['lng']
            ), 2)
        
        result.append(location_info)
    
    # Sort by distance if available
    if lat is not None and lng is not None:
        result.sort(key=lambda x: x['distance_miles'] if x['distance_miles'] is not None else float('inf'))
    
    return {
        "dispensary": dispensary,
        "locations": result,
        "total": len(result),
        "user_location": {"lat": lat, "lng": lng} if lat is not None and lng is not None else None,
        "sorted_by_distance": bool(lat is not None and lng is not None)
    }


@router.get("/{dispensary}")
async def get_dispensary_stock(
    dispensary: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, description="Max results to return", le=500)
):
    """Get all stock for a specific dispensary."""
    index = get_stock_index()
    
    # Get dispensary items (case insensitive)
    dispensary_lower = dispensary.lower()
    dispensary_items = index["by_dispensary"].get(dispensary_lower, [])
    
    if not dispensary_items:
        return {
            "dispensary": dispensary,
            "found": False,
            "total": 0,
            "items": [],
            "message": f"No inventory found for dispensary '{dispensary}'"
        }
    
    # Apply category filter
    filtered = dispensary_items
    if category:
        filtered = [item for item in filtered if item.get("category", "").lower() == category.lower()]
    
    # Apply limit
    filtered = filtered[:limit]
    
    return {
        "dispensary": dispensary,
        "found": True,
        "total": len(filtered),
        "total_unfiltered": len(dispensary_items),
        "items": filtered
    }


@router.get("/{dispensary}/{batch_id}")
async def get_batch_stock(dispensary: str, batch_id: str):
    """Get stock information for a specific batch at a dispensary."""
    index = get_stock_index()
    
    # Search through dispensary's items
    dispensary_items = index["by_dispensary"].get(dispensary.lower(), [])
    
    # Find matching batch
    for item in dispensary_items:
        if item["batch_id"] == batch_id:
            return {
                "found": True,
                "batch": item,
                "dispensary": dispensary,
                "batch_id": batch_id
            }
    
    raise HTTPException(
        status_code=404,
        detail=f"Batch {batch_id} not found at {dispensary}"
    )


@router.post("/{dispensary}")
async def bulk_stock_check(dispensary: str, request: BulkStockRequest):
    """Check stock for multiple batches at once."""
    index = get_stock_index()
    
    dispensary_items = index["by_dispensary"].get(dispensary.lower(), [])
    
    # Build lookup map
    batch_map = {item["batch_id"]: item for item in dispensary_items}
    
    # Check each requested batch
    results = []
    for batch_id in request.batch_ids:
        if batch_id in batch_map:
            results.append({
                "batch_id": batch_id,
                "found": True,
                "item": batch_map[batch_id]
            })
        else:
            results.append({
                "batch_id": batch_id,
                "found": False,
                "item": None
            })
    
    return {
        "dispensary": dispensary,
        "requested": len(request.batch_ids),
        "found": sum(1 for r in results if r["found"]),
        "results": results
    }


@router.post("/build-index")
async def build_stock_index(
    date: Optional[str] = Query(None, description="Date to build from (YYYYMMDD)")
):
    """Rebuild the stock index from batch files."""
    try:
        indexer = get_indexer()
        
        if date:
            logger.info(f"Building stock index from date: {date}")
            index = indexer.build_index_from_date(date)
        else:
            logger.info("Building stock index from latest batch file")
            index = indexer.build_index_from_latest()
        
        # Save index
        path = indexer.save_index(index)
        
        metadata = index["metadata"]
        
        return {
            "success": True,
            "index_path": path,
            "metadata": metadata,
            "message": f"Stock index built with {metadata['total_items']} items from {metadata['unique_strains']} strains"
        }
        
    except Exception as e:
        logger.error(f"Failed to build stock index: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build stock index: {str(e)}"
        )

@router.get("/nearest")
async def get_nearest_stock(
    strain: str = Query(..., description="Strain name to search for"),
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    max_distance: float = Query(50, description="Max distance in miles", le=100),
    limit: int = Query(10, description="Max results to return", le=50)
):
    """Find nearest dispensaries carrying a specific strain."""
    index = get_stock_index()
    indexer = get_indexer()
    
    strain_normalized = indexer.normalize_strain_name(strain)
    items = index["by_strain"].get(strain_normalized, [])
    
    if not items:
        return {
            "strain": strain,
            "user_location": {"lat": lat, "lng": lng},
            "max_distance_miles": max_distance,
            "nearest_locations": [],
            "total_found": 0,
            "message": f"No products found for strain '{strain}'"
        }
    
    # Filter to items with location data
    items_with_location = [
        item for item in items 
        if item.get('latitude') is not None and item.get('longitude') is not None
    ]
    
    # Calculate distances
    for item in items_with_location:
        item['distance_miles'] = round(indexer.calculate_distance(
            lat, lng, item['latitude'], item['longitude']
        ), 2)
    
    # Filter by max distance
    nearby_items = [
        item for item in items_with_location 
        if item['distance_miles'] <= max_distance
    ]
    
    # Sort by distance
    nearby_items.sort(key=lambda x: x['distance_miles'])
    
    return {
        "strain": strain,
        "strain_normalized": strain_normalized,
        "user_location": {"lat": lat, "lng": lng},
        "max_distance_miles": max_distance,
        "nearest_locations": nearby_items[:limit],
        "total_found": len(nearby_items),
        "total_within_radius": len(nearby_items)
    }


@router.post("/run")
async def manual_menu_download():
    """Trigger manual menu download (alias)."""
    return {
        "message": "Use POST /run endpoint for manual downloads",
        "redirect": "/run"
    }


@router.post("/match-batches")
async def match_batches():
    """Match batches to current inventory (not yet implemented)."""
    raise HTTPException(
        status_code=501,
        detail="Batch matching not yet implemented"
    )
