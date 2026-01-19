"""
Genetics Data Models for Terprint Menu Downloader

CDES-compatible dataclasses for strain genetics/lineage information.
Aligned with terprint-config/cannabis-genetics-scraper and CDES v1.0 spec.

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
import re


class StrainType(str, Enum):
    """Cannabis strain classification (CDES-aligned)."""
    INDICA = "indica"
    SATIVA = "sativa"
    HYBRID = "hybrid"
    CBD = "cbd"
    UNKNOWN = "unknown"


@dataclass
class StrainGenetics:
    """
    Strain genetics/lineage data extracted from dispensary products.
    
    Compatible with terprint-config cannabis-genetics-scraper StrainGenetics model.
    """
    strain_name: str
    strain_slug: str
    parent_1: Optional[str] = None
    parent_2: Optional[str] = None
    breeder: Optional[str] = None
    strain_type: Optional[str] = None  # indica, sativa, hybrid
    indica_pct: Optional[int] = None
    sativa_pct: Optional[int] = None
    thc_min: Optional[float] = None
    thc_max: Optional[float] = None
    cbd_min: Optional[float] = None
    cbd_max: Optional[float] = None
    effects: List[str] = field(default_factory=list)
    flavors: List[str] = field(default_factory=list)
    aromas: List[str] = field(default_factory=list)
    description: Optional[str] = None
    lineage: List[str] = field(default_factory=list)  # Full lineage tree
    
    # Source tracking
    source_dispensary: Optional[str] = None
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    terprint_match: bool = True  # Indicates this came from Terprint dispensary data
    
    @staticmethod
    def normalize_strain_name(name: str) -> str:
        """
        Convert strain name to a normalized slug.
        
        Examples:
            "Blue Dream" -> "blue-dream"
            "OG Kush #18" -> "og-kush-18"
            "Girl Scout Cookies (GSC)" -> "girl-scout-cookies-gsc"
        """
        if not name:
            return ""
        slug = name.lower().strip()
        # Remove parentheses content but keep if it's an abbreviation
        slug = re.sub(r'\s*\(([^)]+)\)\s*', r'-\1-', slug)
        # Replace special chars with hyphen
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        # Collapse multiple hyphens
        slug = re.sub(r'-+', '-', slug)
        return slug
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "strain_name": self.strain_name,
            "strain_slug": self.strain_slug,
            "parent_1": self.parent_1,
            "parent_2": self.parent_2,
            "breeder": self.breeder,
            "strain_type": self.strain_type,
            "indica_pct": self.indica_pct,
            "sativa_pct": self.sativa_pct,
            "thc_min": self.thc_min,
            "thc_max": self.thc_max,
            "cbd_min": self.cbd_min,
            "cbd_max": self.cbd_max,
            "effects": self.effects,
            "flavors": self.flavors,
            "aromas": self.aromas,
            "description": self.description,
            "lineage": self.lineage,
            "source_dispensary": self.source_dispensary,
            "source_file": self.source_file,
            "source_url": self.source_url,
            "scraped_at": self.scraped_at,
            "terprint_match": self.terprint_match,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrainGenetics":
        """Create from dictionary."""
        return cls(
            strain_name=data.get("strain_name", ""),
            strain_slug=data.get("strain_slug", ""),
            parent_1=data.get("parent_1"),
            parent_2=data.get("parent_2"),
            breeder=data.get("breeder"),
            strain_type=data.get("strain_type"),
            indica_pct=data.get("indica_pct"),
            sativa_pct=data.get("sativa_pct"),
            thc_min=data.get("thc_min"),
            thc_max=data.get("thc_max"),
            cbd_min=data.get("cbd_min"),
            cbd_max=data.get("cbd_max"),
            effects=data.get("effects", []),
            flavors=data.get("flavors", []),
            aromas=data.get("aromas", []),
            description=data.get("description"),
            lineage=data.get("lineage", []),
            source_dispensary=data.get("source_dispensary"),
            source_file=data.get("source_file"),
            source_url=data.get("source_url"),
            scraped_at=data.get("scraped_at", datetime.now(timezone.utc).isoformat()),
            terprint_match=data.get("terprint_match", True),
        )


@dataclass
class CDESGenetics:
    """
    CDES-compliant genetics format for strain data.
    
    This is the format used in CDES Strain.genetics field:
    {
        "lineage": ["Parent1", "Parent2"],
        "breeder": "Breeder Name",
        "cross": "Parent1 x Parent2"
    }
    """
    lineage: List[str] = field(default_factory=list)
    breeder: Optional[str] = None
    cross: Optional[str] = None  # Formatted as "Parent1 x Parent2"
    
    @classmethod
    def from_strain_genetics(cls, genetics: StrainGenetics) -> "CDESGenetics":
        """Convert StrainGenetics to CDES format."""
        lineage = []
        cross = None
        
        if genetics.parent_1:
            lineage.append(genetics.parent_1)
        if genetics.parent_2:
            lineage.append(genetics.parent_2)
        
        if genetics.parent_1 and genetics.parent_2:
            cross = f"{genetics.parent_1} x {genetics.parent_2}"
        
        # If we have a full lineage tree, use that instead
        if genetics.lineage:
            lineage = genetics.lineage
        
        return cls(
            lineage=lineage,
            breeder=genetics.breeder,
            cross=cross,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to CDES-compliant dictionary."""
        result = {}
        if self.lineage:
            result["lineage"] = self.lineage
        if self.breeder:
            result["breeder"] = self.breeder
        if self.cross:
            result["cross"] = self.cross
        return result


@dataclass
class GeneticsExtractionResult:
    """
    Result of a genetics extraction operation.
    
    Tracks statistics and results from processing menu data.
    """
    total_products: int = 0
    products_with_strain: int = 0
    products_with_genetics: int = 0
    unique_strains: int = 0
    genetics_found: List[StrainGenetics] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    source_file: Optional[str] = None
    dispensary: Optional[str] = None
    processed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_products": self.total_products,
            "products_with_strain": self.products_with_strain,
            "products_with_genetics": self.products_with_genetics,
            "unique_strains": self.unique_strains,
            "genetics_found": [g.to_dict() for g in self.genetics_found],
            "errors": self.errors,
            "source_file": self.source_file,
            "dispensary": self.dispensary,
            "processed_at": self.processed_at,
        }
