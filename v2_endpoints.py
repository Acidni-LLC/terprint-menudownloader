"""
CDES v2 API Endpoints for Terprint Data API

These endpoints return data in CDES (Cannabis Data Exchange Standard) format.
They run alongside the v1 endpoints for backwards compatibility.

v1 endpoints: /api/strains, /api/batches, etc. (legacy format)
v2 endpoints: /v2/strains, /v2/batches, etc. (CDES format)

Usage:
    # Import and register with main app
    from v2_endpoints import register_v2_endpoints
    register_v2_endpoints(app)
"""

import azure.functions as func
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# CDES Models (from cdes-sdk-python or inline if not installed)
try:
    from cdes import Strain, Batch, TerpeneProfile, TerpeneEntry, CannabinoidProfile, CannabinoidEntry
    from cdes import StrainType, ProductCategory, ConcentrationUnit
    CDES_SDK_AVAILABLE = True
except ImportError:
    CDES_SDK_AVAILABLE = False
    # Inline CDES-compatible models for when SDK isn't installed
    from dataclasses import dataclass, field, asdict
    from enum import Enum
    
    class StrainType(str, Enum):
        INDICA = "indica"
        SATIVA = "sativa"
        HYBRID = "hybrid"
        UNKNOWN = "unknown"
    
    class ConcentrationUnit(str, Enum):
        PERCENT = "percent"
        MG_G = "mg_per_gram"
        MG_ML = "mg_per_ml"
        PPM = "ppm"
    
    @dataclass
    class TerpeneEntry:
        compound: str
        value: float
        unit: ConcentrationUnit = ConcentrationUnit.PERCENT
        
        def to_dict(self) -> dict:
            return {"compound": self.compound, "value": self.value, "unit": self.unit.value}
    
    @dataclass
    class TerpeneProfile:
        entries: List[TerpeneEntry] = field(default_factory=list)
        total_terpenes_pct: Optional[float] = None
        dominant_terpene: Optional[str] = None
        
        def to_dict(self) -> dict:
            return {
                "entries": [e.to_dict() for e in self.entries],
                "total_terpenes_pct": self.total_terpenes_pct,
                "dominant_terpene": self.dominant_terpene
            }
    
    @dataclass
    class CannabinoidEntry:
        compound: str
        value: float
        unit: ConcentrationUnit = ConcentrationUnit.PERCENT
        
        def to_dict(self) -> dict:
            return {"compound": self.compound, "value": self.value, "unit": self.unit.value}
    
    @dataclass
    class CannabinoidProfile:
        thc_pct: Optional[float] = None
        cbd_pct: Optional[float] = None
        entries: List[CannabinoidEntry] = field(default_factory=list)
        
        def to_dict(self) -> dict:
            return {
                "thc_pct": self.thc_pct,
                "cbd_pct": self.cbd_pct,
                "entries": [e.to_dict() for e in self.entries]
            }
    
    @dataclass
    class Strain:
        id: str
        name: str
        strain_type: StrainType = StrainType.UNKNOWN
        genetics: Dict[str, Any] = field(default_factory=dict)
        terpene_profile: Optional[TerpeneProfile] = None
        cannabinoid_profile: Optional[CannabinoidProfile] = None
        metadata: Dict[str, Any] = field(default_factory=dict)
        
        def to_dict(self) -> dict:
            return {
                "$schema": "https://cdes.terprint.com/v1/strain.schema.json",
                "cdes_version": "1.0.0",
                "id": self.id,
                "name": self.name,
                "strain_type": self.strain_type.value if isinstance(self.strain_type, StrainType) else self.strain_type,
                "genetics": self.genetics,
                "terpene_profile": self.terpene_profile.to_dict() if self.terpene_profile else None,
                "cannabinoid_profile": self.cannabinoid_profile.to_dict() if self.cannabinoid_profile else None,
                "metadata": self.metadata
            }
    
    @dataclass
    class Batch:
        id: str
        batch_number: str
        strain_id: str
        strain_name: str
        dispensary_id: int
        dispensary_name: str
        harvest_date: Optional[str] = None
        test_date: Optional[str] = None
        terpene_profile: Optional[TerpeneProfile] = None
        cannabinoid_profile: Optional[CannabinoidProfile] = None
        metadata: Dict[str, Any] = field(default_factory=dict)
        
        def to_dict(self) -> dict:
            return {
                "$schema": "https://cdes.terprint.com/v1/batch.schema.json",
                "cdes_version": "1.0.0",
                "id": self.id,
                "batch_number": self.batch_number,
                "strain_id": self.strain_id,
                "strain_name": self.strain_name,
                "dispensary_id": self.dispensary_id,
                "dispensary_name": self.dispensary_name,
                "harvest_date": self.harvest_date,
                "test_date": self.test_date,
                "terpene_profile": self.terpene_profile.to_dict() if self.terpene_profile else None,
                "cannabinoid_profile": self.cannabinoid_profile.to_dict() if self.cannabinoid_profile else None,
                "metadata": self.metadata
            }

from terprint_config.middleware import require_backend_api_key
from terprint_config import settings

# Import shared utilities from main function_app
# These will be available when this module is imported into function_app.py


CDES_VERSION = "1.0.0"
API_VERSION = "v2"


def cdes_headers() -> dict:
    """Standard CDES response headers."""
    return {
        "X-CDES-Version": CDES_VERSION,
        "X-API-Version": API_VERSION,
        "Content-Type": "application/json"
    }


def json_response(data: Any, status_code: int = 200) -> func.HttpResponse:
    """Create JSON response with CDES headers."""
    return func.HttpResponse(
        body=json.dumps(data, default=str),
        status_code=status_code,
        headers=cdes_headers()
    )


def error_response(code: str, message: str, status_code: int, request_id: str = None, details: dict = None) -> func.HttpResponse:
    """Create error response with CDES headers."""
    body = {
        "error": code,
        "message": message,
        "cdes_version": CDES_VERSION,
        "api_version": API_VERSION
    }
    if request_id:
        body["request_id"] = request_id
    if details:
        body["details"] = details
    
    return func.HttpResponse(
        body=json.dumps(body),
        status_code=status_code,
        headers=cdes_headers()
    )


def convert_strain_to_cdes(legacy_strain: dict, terpenes: List[dict] = None, cannabinoids: List[dict] = None) -> Strain:
    """Convert legacy strain dict to CDES Strain model."""
    
    # Map legacy strain type to CDES enum
    strain_type_map = {
        "Indica": StrainType.INDICA,
        "indica": StrainType.INDICA,
        "Sativa": StrainType.SATIVA,
        "sativa": StrainType.SATIVA,
        "Hybrid": StrainType.HYBRID,
        "hybrid": StrainType.HYBRID,
    }
    strain_type = strain_type_map.get(legacy_strain.get("strainType") or legacy_strain.get("type"), StrainType.UNKNOWN)
    
    # Build terpene profile if data provided
    terpene_profile = None
    if terpenes:
        entries = [
            TerpeneEntry(
                compound=t.get("terpene_name") or t.get("name"),
                value=float(t.get("percentage") or t.get("value") or 0),
                unit=ConcentrationUnit.PERCENT
            )
            for t in terpenes if t.get("percentage") or t.get("value")
        ]
        if entries:
            total = sum(e.value for e in entries)
            dominant = max(entries, key=lambda x: x.value).compound if entries else None
            terpene_profile = TerpeneProfile(
                entries=entries,
                total_terpenes_pct=round(total, 3),
                dominant_terpene=dominant
            )
    
    # Build cannabinoid profile if data provided
    cannabinoid_profile = None
    if cannabinoids:
        entries = [
            CannabinoidEntry(
                compound=c.get("cannabinoid_name") or c.get("name"),
                value=float(c.get("percentage") or c.get("value") or 0),
                unit=ConcentrationUnit.PERCENT
            )
            for c in cannabinoids if c.get("percentage") or c.get("value")
        ]
        if entries:
            thc = next((e.value for e in entries if e.compound.upper() in ["THC", "THCA", "D9-THC"]), None)
            cbd = next((e.value for e in entries if e.compound.upper() in ["CBD", "CBDA"]), None)
            cannabinoid_profile = CannabinoidProfile(
                thc_pct=thc,
                cbd_pct=cbd,
                entries=entries
            )
    
    return Strain(
        id=str(legacy_strain.get("id") or legacy_strain.get("strainId")),
        name=legacy_strain.get("name") or legacy_strain.get("strainName"),
        strain_type=strain_type,
        genetics={
            "lineage": legacy_strain.get("lineage", []),
            "breeder": legacy_strain.get("breeder")
        },
        terpene_profile=terpene_profile,
        cannabinoid_profile=cannabinoid_profile,
        metadata={
            "source": "terprint",
            "created_at": legacy_strain.get("createdAt") or datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
    )


def convert_batch_to_cdes(legacy_batch: dict, terpenes: List[dict] = None, cannabinoids: List[dict] = None) -> Batch:
    """Convert legacy batch dict to CDES Batch model."""
    
    # Build terpene profile
    terpene_profile = None
    if terpenes:
        entries = [
            TerpeneEntry(
                compound=t.get("terpene_name") or t.get("name"),
                value=float(t.get("percentage") or t.get("value") or 0),
                unit=ConcentrationUnit.PERCENT
            )
            for t in terpenes if t.get("percentage") or t.get("value")
        ]
        if entries:
            total = sum(e.value for e in entries)
            dominant = max(entries, key=lambda x: x.value).compound if entries else None
            terpene_profile = TerpeneProfile(
                entries=entries,
                total_terpenes_pct=round(total, 3),
                dominant_terpene=dominant
            )
    
    # Build cannabinoid profile
    cannabinoid_profile = None
    thc = legacy_batch.get("thc") or legacy_batch.get("thcPercentage")
    cbd = legacy_batch.get("cbd") or legacy_batch.get("cbdPercentage")
    if thc is not None or cbd is not None or cannabinoids:
        entries = []
        if thc is not None:
            entries.append(CannabinoidEntry(compound="THC", value=float(thc), unit=ConcentrationUnit.PERCENT))
        if cbd is not None:
            entries.append(CannabinoidEntry(compound="CBD", value=float(cbd), unit=ConcentrationUnit.PERCENT))
        if cannabinoids:
            for c in cannabinoids:
                name = c.get("cannabinoid_name") or c.get("name")
                if name and name.upper() not in ["THC", "CBD"]:
                    entries.append(CannabinoidEntry(
                        compound=name,
                        value=float(c.get("percentage") or c.get("value") or 0),
                        unit=ConcentrationUnit.PERCENT
                    ))
        cannabinoid_profile = CannabinoidProfile(
            thc_pct=float(thc) if thc else None,
            cbd_pct=float(cbd) if cbd else None,
            entries=entries
        )
    
    return Batch(
        id=str(legacy_batch.get("id") or legacy_batch.get("batchId")),
        batch_number=legacy_batch.get("batchNumber") or legacy_batch.get("batch_number"),
        strain_id=str(legacy_batch.get("strainId") or legacy_batch.get("strain_id")),
        strain_name=legacy_batch.get("strainName") or legacy_batch.get("strain_name"),
        dispensary_id=int(legacy_batch.get("growerId") or legacy_batch.get("dispensaryId") or 0),
        dispensary_name=legacy_batch.get("growerName") or legacy_batch.get("dispensaryName"),
        harvest_date=legacy_batch.get("harvestDate"),
        test_date=legacy_batch.get("testDate") or legacy_batch.get("createdAt"),
        terpene_profile=terpene_profile,
        cannabinoid_profile=cannabinoid_profile,
        metadata={
            "source": "terprint",
            "dispensary_batch_id": legacy_batch.get("dispensaryBatchId"),
            "created_at": legacy_batch.get("createdAt") or datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
    )


def register_v2_endpoints(app: func.FunctionApp, data_service):
    """
    Register all v2 CDES endpoints with the function app.
    
    Args:
        app: Azure Functions FunctionApp instance
        data_service: Data service instance with database access methods
    """
    
    # =========================================================================
    # v2/strains - CDES Strain endpoints
    # =========================================================================
    
    @app.route(route="v2/strains", methods=["GET"])
    @require_backend_api_key
    async def get_strains_v2(req: func.HttpRequest) -> func.HttpResponse:
        """
        List strains in CDES format.
        
        Query Parameters:
            - type: Filter by strain type (indica, sativa, hybrid)
            - limit: Max results (default 50, max 100)
            - offset: Pagination offset
            - include: Comma-separated includes (terpenes, cannabinoids)
        """
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            type_filter = req.params.get("type")
            limit = min(int(req.params.get("limit", 50)), 100)
            offset = int(req.params.get("offset", 0))
            includes = (req.params.get("include") or "").split(",")
            include_terpenes = "terpenes" in includes
            include_cannabinoids = "cannabinoids" in includes
            
            # Get strains from database
            strains, total = await data_service.get_strains(
                type_filter=type_filter,
                limit=limit,
                offset=offset
            )
            
            # Convert to CDES format
            cdes_strains = []
            for s in strains:
                terpenes = None
                cannabinoids = None
                
                if include_terpenes:
                    # Get terpene data for strain's batches
                    terpenes = await data_service.get_strain_terpenes(s.get("id"))
                
                if include_cannabinoids:
                    cannabinoids = await data_service.get_strain_cannabinoids(s.get("id"))
                
                cdes_strain = convert_strain_to_cdes(s, terpenes, cannabinoids)
                cdes_strains.append(cdes_strain.to_dict())
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return json_response({
                "data": cdes_strains,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + len(cdes_strains)) < total
                },
                "meta": {
                    "cdes_version": CDES_VERSION,
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/strains: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    @app.route(route="v2/strains/{strain_id}", methods=["GET"])
    @require_backend_api_key
    async def get_strain_v2(req: func.HttpRequest) -> func.HttpResponse:
        """Get single strain in CDES format with full terpene/cannabinoid profiles."""
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            strain_id = req.route_params.get("strain_id")
            
            strain = await data_service.get_strain_by_id(strain_id)
            if not strain:
                return error_response("NOT_FOUND", f"Strain {strain_id} not found", 404, request_id)
            
            # Get full profiles
            terpenes = await data_service.get_strain_terpenes(strain_id)
            cannabinoids = await data_service.get_strain_cannabinoids(strain_id)
            
            cdes_strain = convert_strain_to_cdes(strain, terpenes, cannabinoids)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return json_response({
                "data": cdes_strain.to_dict(),
                "meta": {
                    "cdes_version": CDES_VERSION,
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/strains/{strain_id}: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    # =========================================================================
    # v2/batches - CDES Batch endpoints
    # =========================================================================
    
    @app.route(route="v2/batches", methods=["GET"])
    @require_backend_api_key
    async def get_batches_v2(req: func.HttpRequest) -> func.HttpResponse:
        """
        List batches in CDES format.
        
        Query Parameters:
            - dispensary: Filter by dispensary ID or name
            - strain: Filter by strain ID or name
            - limit: Max results (default 50, max 100)
            - offset: Pagination offset
        """
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            dispensary = req.params.get("dispensary")
            strain = req.params.get("strain")
            limit = min(int(req.params.get("limit", 50)), 100)
            offset = int(req.params.get("offset", 0))
            
            batches, total = await data_service.get_batches(
                dispensary=dispensary,
                strain=strain,
                limit=limit,
                offset=offset
            )
            
            # Convert to CDES format with profiles
            cdes_batches = []
            for b in batches:
                batch_id = b.get("id") or b.get("batchId")
                terpenes = await data_service.get_terpene_profile(batch_id)
                cannabinoids = await data_service.get_cannabinoid_profile(batch_id)
                
                cdes_batch = convert_batch_to_cdes(b, terpenes, cannabinoids)
                cdes_batches.append(cdes_batch.to_dict())
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return json_response({
                "data": cdes_batches,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + len(cdes_batches)) < total
                },
                "meta": {
                    "cdes_version": CDES_VERSION,
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/batches: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    @app.route(route="v2/batches/{batch_id}", methods=["GET"])
    @require_backend_api_key
    async def get_batch_v2(req: func.HttpRequest) -> func.HttpResponse:
        """Get single batch in CDES format with full profiles."""
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            batch_id = req.route_params.get("batch_id")
            
            batch = await data_service.get_batch_by_id(batch_id)
            if not batch:
                return error_response("NOT_FOUND", f"Batch {batch_id} not found", 404, request_id)
            
            terpenes = await data_service.get_terpene_profile(batch_id)
            cannabinoids = await data_service.get_cannabinoid_profile(batch_id)
            
            cdes_batch = convert_batch_to_cdes(batch, terpenes, cannabinoids)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return json_response({
                "data": cdes_batch.to_dict(),
                "meta": {
                    "cdes_version": CDES_VERSION,
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/batches/{batch_id}: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    # =========================================================================
    # v2/terpene-profiles - CDES TerpeneProfile endpoints
    # =========================================================================
    
    @app.route(route="v2/terpene-profiles/{batch_id}", methods=["GET"])
    @require_backend_api_key
    async def get_terpene_profile_v2(req: func.HttpRequest) -> func.HttpResponse:
        """Get terpene profile for a batch in CDES format."""
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            batch_id = req.route_params.get("batch_id")
            
            terpenes = await data_service.get_terpene_profile(batch_id)
            if not terpenes:
                return error_response("NOT_FOUND", f"Terpene profile for batch {batch_id} not found", 404, request_id)
            
            # Build CDES TerpeneProfile
            entries = [
                TerpeneEntry(
                    compound=t.get("terpene_name") or t.get("name"),
                    value=float(t.get("percentage") or t.get("value") or 0),
                    unit=ConcentrationUnit.PERCENT
                )
                for t in terpenes if t.get("percentage") or t.get("value")
            ]
            
            total = sum(e.value for e in entries)
            dominant = max(entries, key=lambda x: x.value).compound if entries else None
            
            profile = TerpeneProfile(
                entries=entries,
                total_terpenes_pct=round(total, 3),
                dominant_terpene=dominant
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return json_response({
                "$schema": "https://cdes.terprint.com/v1/terpene-profile.schema.json",
                "cdes_version": CDES_VERSION,
                "batch_id": batch_id,
                "data": profile.to_dict(),
                "meta": {
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/terpene-profiles/{batch_id}: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    # =========================================================================
    # v2/cannabinoid-profiles - CDES CannabinoidProfile endpoints
    # =========================================================================
    
    @app.route(route="v2/cannabinoid-profiles/{batch_id}", methods=["GET"])
    @require_backend_api_key
    async def get_cannabinoid_profile_v2(req: func.HttpRequest) -> func.HttpResponse:
        """Get cannabinoid profile for a batch in CDES format."""
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            batch_id = req.route_params.get("batch_id")
            
            cannabinoids = await data_service.get_cannabinoid_profile(batch_id)
            if not cannabinoids:
                return error_response("NOT_FOUND", f"Cannabinoid profile for batch {batch_id} not found", 404, request_id)
            
            # Build CDES CannabinoidProfile
            entries = [
                CannabinoidEntry(
                    compound=c.get("cannabinoid_name") or c.get("name"),
                    value=float(c.get("percentage") or c.get("value") or 0),
                    unit=ConcentrationUnit.PERCENT
                )
                for c in cannabinoids if c.get("percentage") or c.get("value")
            ]
            
            thc = next((e.value for e in entries if e.compound.upper() in ["THC", "THCA", "D9-THC"]), None)
            cbd = next((e.value for e in entries if e.compound.upper() in ["CBD", "CBDA"]), None)
            
            profile = CannabinoidProfile(
                thc_pct=thc,
                cbd_pct=cbd,
                entries=entries
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return json_response({
                "$schema": "https://cdes.terprint.com/v1/cannabinoid-profile.schema.json",
                "cdes_version": CDES_VERSION,
                "batch_id": batch_id,
                "data": profile.to_dict(),
                "meta": {
                    "api_version": API_VERSION,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/cannabinoid-profiles/{batch_id}: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    # =========================================================================
    # v2/search - CDES-formatted search
    # =========================================================================
    
    @app.route(route="v2/search", methods=["GET"])
    @require_backend_api_key
    async def search_v2(req: func.HttpRequest) -> func.HttpResponse:
        """
        Full-text search returning CDES-formatted results.
        
        Query Parameters:
            - q: Search query (required)
            - type: Result types (strain, batch) - default: all
            - limit: Max results per type (default 20, max 50)
        """
        request_id = req.headers.get("x-request-id", "")
        start_time = datetime.utcnow()
        
        try:
            query = req.params.get("q")
            if not query:
                return error_response("INVALID_REQUEST", "Query parameter 'q' is required", 400, request_id)
            
            types = (req.params.get("type") or "strain,batch").split(",")
            limit = min(int(req.params.get("limit", 20)), 50)
            
            results = await data_service.search(query=query, types=types, limit=limit)
            
            # Convert results to CDES format
            cdes_results = {
                "strains": [],
                "batches": []
            }
            
            if "strain" in types and results.get("strain"):
                for s in results["strain"]:
                    cdes_strain = convert_strain_to_cdes(s)
                    cdes_results["strains"].append(cdes_strain.to_dict())
            
            if "batch" in types and results.get("batch"):
                for b in results["batch"]:
                    cdes_batch = convert_batch_to_cdes(b)
                    cdes_results["batches"].append(cdes_batch.to_dict())
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            total_results = len(cdes_results["strains"]) + len(cdes_results["batches"])
            
            return json_response({
                "data": cdes_results,
                "meta": {
                    "cdes_version": CDES_VERSION,
                    "api_version": API_VERSION,
                    "query": query,
                    "total_results": total_results,
                    "request_id": request_id,
                    "processing_time_ms": round(processing_time, 2)
                }
            })
            
        except Exception as e:
            logging.error(f"Error in v2/search: {e}")
            return error_response("INTERNAL_ERROR", str(e), 500, request_id)
    
    
    # =========================================================================
    # v2/health - Health check with CDES info
    # =========================================================================
    
    @app.route(route="v2/health", methods=["GET"])
    async def health_v2(req: func.HttpRequest) -> func.HttpResponse:
        """Health check endpoint for v2 API."""
        return json_response({
            "status": "healthy",
            "api_version": API_VERSION,
            "cdes_version": CDES_VERSION,
            "cdes_sdk_installed": CDES_SDK_AVAILABLE,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    
    logging.info(f"Registered CDES v2 endpoints (CDES SDK available: {CDES_SDK_AVAILABLE})")
