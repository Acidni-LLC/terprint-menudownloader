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
    limit: int = Query(50, description="Max results to return", le=200)
):
    """Search for products by strain name across all dispensaries."""
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
    
    # Limit results
    filtered = filtered[:limit]
    
    return {
        "strain": strain,
        "strain_normalized": strain_normalized,
        "matches": filtered,
        "total": len(filtered),
        "total_all_dispensaries": len(items)
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
