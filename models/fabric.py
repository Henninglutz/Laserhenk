"""Fabric Data Models for HENK System.

Simplified Pydantic models based on existing SQLAlchemy schema.
Only includes fields relevant for agent handoffs and RAG queries.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Season(str, Enum):
    """Fabric seasons."""

    WEDDING = "wedding"
    SUMMER = "summer"
    FOUR_SEASON = "4season"
    WINTER = "winter"


class StockStatus(str, Enum):
    """Stock availability status."""

    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    ON_ORDER = "on_order"


class FabricPattern(str, Enum):
    """Common fabric patterns."""

    UNI = "uni"  # Solid/plain
    FISCHGRAT = "fischgrat"  # Herringbone
    KARO = "karo"  # Check
    NADELSTREIFEN = "nadelstreifen"  # Pinstripe
    KREIDESTREIFEN = "kreidestreifen"  # Chalk stripe
    GLEN_CHECK = "glen_check"
    PEPITA = "pepita"  # Houndstooth
    TWILL = "twill"
    STRUKTUR = "struktur"  # Textured


class FabricColor(str, Enum):
    """Common fabric colors."""

    NAVY = "navy"
    GRAU = "grau"  # Gray
    SCHWARZ = "schwarz"  # Black
    DUNKELBLAU = "dunkelblau"  # Dark blue
    HELLGRAU = "hellgrau"  # Light gray
    MITTELGRAU = "mittelgrau"  # Medium gray
    ANTHRAZIT = "anthrazit"
    BRAUN = "braun"  # Brown
    BEIGE = "beige"
    OLIV = "oliv"  # Olive


class FabricData(BaseModel):
    """
    Simplified Fabric Data Model.

    Based on SQLAlchemy Fabric model but simplified for agent handoffs.
    """

    fabric_code: str = Field(..., description="Unique fabric code")
    name: str = Field(..., description="Fabric name")

    # Core characteristics
    composition: Optional[str] = Field(
        None, description="e.g., '100% Wool', 'Super 150s'"
    )
    weight: Optional[int] = Field(None, description="Weight in g/m²", gt=0)
    color: Optional[str] = Field(None, description="Primary color")
    pattern: Optional[str] = Field(None, description="Pattern type")

    # Categorization
    category: Optional[str] = Field(
        None, description="Fabric category (e.g., 'suiting', 'casual')"
    )
    seasons: list[Season] = Field(
        default_factory=list, description="Suitable seasons"
    )

    # Availability
    stock_status: Optional[str] = Field(None, description="Stock status")
    supplier: str = Field(default="Formens", description="Supplier name")

    # Metadata
    description: Optional[str] = Field(
        None, description="Human-readable description"
    )
    image_urls: list[str] = Field(
        default_factory=list, description="Fabric image URLs"
    )

    # RAG-relevant
    price_category: Optional[str] = Field(
        None, description="Price category (for budget filtering)"
    )

    model_config = ConfigDict(use_enum_values=True)


class FabricSearchCriteria(BaseModel):
    """
    Search criteria for fabric RAG queries.

    Used by agents to query the fabric database.
    """

    # From HENK1 handoff
    colors: Optional[list[str]] = Field(
        None, description="Preferred colors"
    )
    patterns: Optional[list[str]] = Field(
        None, description="Preferred patterns"
    )
    season: Optional[Season] = Field(
        None, description="Season requirement"
    )
    occasion: Optional[str] = Field(
        None, description="Occasion (e.g., 'wedding', 'business')"
    )

    # Budget filtering
    budget_min: Optional[float] = Field(None, description="Min budget EUR")
    budget_max: Optional[float] = Field(None, description="Max budget EUR")

    # Stock requirement
    in_stock_only: bool = Field(
        default=True, description="Only show in-stock fabrics"
    )

    # Limit results
    limit: int = Field(
        default=10, description="Max number of results", ge=1, le=50
    )


class FabricRecommendation(BaseModel):
    """
    Fabric recommendation result from RAG.

    Returned to agents after RAG query.
    """

    fabric: FabricData
    similarity_score: float = Field(
        ..., description="Similarity score (0-1)", ge=0, le=1
    )
    match_reasons: list[str] = Field(
        default_factory=list,
        description="Why this fabric was recommended",
    )
