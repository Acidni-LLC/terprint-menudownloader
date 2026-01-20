"""
Terprint Menu Downloader - Azure Function App
Downloads menu data from Florida dispensaries and serves CDES v2 API endpoints.

Security: All HTTP endpoints (except /health and /v2/health) require X-Backend-Api-Key header.
APIM injects this header on all requests routed through the gateway.
"""

import azure.functions as func
import logging
import json
import os
from datetime import datetime, timezone

from terprint_config.middleware import require_backend_api_key

# Create the main function app
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ============================================================================
# Health Check Endpoint (NO API KEY REQUIRED - for load balancer probes)
# ============================================================================

@app.route(route="health", methods=["GET"])
async def health(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint for load balancer and monitoring probes.
    
    This endpoint is intentionally NOT protected by API key validation
    to allow Azure load balancers and health probes to check service status.
    
    Returns:
        200 OK with JSON status payload
    """
    return func.HttpResponse(
        body=json.dumps({
            "status": "healthy",
            "service": "terprint-menudownloader",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": os.environ.get("APP_VERSION", "1.0.0"),
            "endpoint_type": "main"
        }),
        mimetype="application/json",
        status_code=200
    )


# ============================================================================
# Protected Endpoints (REQUIRE X-Backend-Api-Key header from APIM)
# ============================================================================

@app.route(route="menu/{dispensary}", methods=["GET"])
@require_backend_api_key
async def get_menu(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get menu data for a specific dispensary.
    
    Protected by backend API key validation - only APIM can call this endpoint.
    
    Args:
        dispensary: The dispensary identifier (e.g., 'muv', 'trulieve', 'flowery', 'cookies')
    
    Returns:
        200 OK with menu JSON data
        401 Unauthorized if X-Backend-Api-Key is missing or invalid
        404 Not Found if dispensary not found
    """
    dispensary = req.route_params.get("dispensary", "").lower()
    
    if not dispensary:
        return func.HttpResponse(
            body=json.dumps({"error": "Dispensary parameter is required"}),
            mimetype="application/json",
            status_code=400
        )
    
    logging.info(f"Menu request for dispensary: {dispensary}")
    
    # TODO: Implement actual menu download logic
    # This would call the CLI module or orchestrator
    return func.HttpResponse(
        body=json.dumps({
            "dispensary": dispensary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "products": [],
            "message": "Menu download endpoint - implementation pending"
        }),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="stock-check", methods=["POST"])
@require_backend_api_key
async def stock_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Check stock availability across dispensaries.
    
    Protected by backend API key validation - only APIM can call this endpoint.
    
    Request Body:
        {
            "dispensaries": ["muv", "trulieve"],
            "products": ["Blue Dream", "Jack Herer"]
        }
    
    Returns:
        200 OK with stock availability data
        401 Unauthorized if X-Backend-Api-Key is missing or invalid
        400 Bad Request if request body is invalid
    """
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            body=json.dumps({"error": "Invalid JSON in request body"}),
            mimetype="application/json",
            status_code=400
        )
    
    dispensaries = req_body.get("dispensaries", [])
    products = req_body.get("products", [])
    
    logging.info(f"Stock check request - dispensaries: {dispensaries}, products: {products}")
    
    # TODO: Implement actual stock check logic
    return func.HttpResponse(
        body=json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dispensaries": dispensaries,
            "products": products,
            "availability": {},
            "message": "Stock check endpoint - implementation pending"
        }),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="download", methods=["POST"])
@require_backend_api_key
async def download_menus(req: func.HttpRequest) -> func.HttpResponse:
    """
    Trigger menu download for specified dispensaries.
    
    Protected by backend API key validation - only APIM can call this endpoint.
    
    Request Body:
        {
            "dispensaries": ["muv", "trulieve", "flowery", "cookies"],
            "force_refresh": false
        }
    
    Returns:
        202 Accepted with download job status
        401 Unauthorized if X-Backend-Api-Key is missing or invalid
        400 Bad Request if request body is invalid
    """
    try:
        req_body = req.get_json()
    except ValueError:
        req_body = {}
    
    dispensaries = req_body.get("dispensaries", ["muv", "trulieve", "flowery", "cookies"])
    force_refresh = req_body.get("force_refresh", False)
    
    logging.info(f"Download triggered for dispensaries: {dispensaries}, force_refresh: {force_refresh}")
    
    # TODO: Implement actual download trigger logic
    # This would call the CLI module or orchestrator
    return func.HttpResponse(
        body=json.dumps({
            "status": "accepted",
            "job_id": f"download-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "dispensaries": dispensaries,
            "force_refresh": force_refresh,
            "message": "Download job queued - implementation pending"
        }),
        mimetype="application/json",
        status_code=202
    )


# ============================================================================
# Register CDES v2 Endpoints from v2_endpoints.py
# ============================================================================
try:
    # Import the register_v2_endpoints function
    from v2_endpoints import register_v2_endpoints
    
    # Create a mock data service for now (will be replaced with actual implementation)
    class MockDataService:
        """Mock data service for development/testing."""
        
        async def get_strains(self, **kwargs):
            return []
        
        async def get_strain_by_id(self, strain_id):
            return None
        
        async def get_batches(self, **kwargs):
            return []
        
        async def get_batch_by_id(self, batch_id):
            return None
        
        async def search(self, query):
            return {"results": [], "total": 0}
    
    # Register the v2 endpoints with mock data service
    mock_data_service = MockDataService()
    register_v2_endpoints(app, mock_data_service)
    
    logging.info("Registered CDES v2 endpoints from v2_endpoints.py module")
    
except Exception as e:
    logging.error(f"Failed to register v2 endpoints: {e}")
    # Function app will still work with basic endpoints above