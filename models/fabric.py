"""Fabric Data Models for HENK System.

Simplified Pydantic models based on existing SQLAlchemy schema.
Only includes fields relevant for agent handoffs and RAG queries.
"""

from enum import Enum
from typing import Any, Optional

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
    Extended with scraping and processing metadata.
    """

    fabric_code: str = Field(..., description="Unique fabric code")
    name: Optional[str] = Field(None, description="Fabric name")

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
    seasons: list[Season] = Field(default_factory=list, description="Suitable seasons")

    # Availability
    stock_status: Optional[str] = Field(None, description="Stock status")
    supplier: str = Field(default="Formens", description="Supplier name")
    origin: Optional[str] = Field(None, description="Country of origin")

    # Metadata
    description: Optional[str] = Field(None, description="Human-readable description")
    care_instructions: Optional[str] = Field(
        None, description="Care and maintenance instructions"
    )
    image_urls: list[str] = Field(default_factory=list, description="Fabric image URLs")
    local_image_paths: list[str] = Field(
        default_factory=list, description="Local paths to downloaded images"
    )

    # RAG-relevant
    price_category: Optional[str] = Field(
        None, description="Price category (for budget filtering)"
    )

    # Scraping metadata
    scrape_date: Optional[str] = Field(
        None, description="ISO timestamp of when data was scraped"
    )
    additional_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional flexible metadata"
    )

    model_config = ConfigDict(use_enum_values=True)


class FabricSearchCriteria(BaseModel):
    """
    Search criteria for fabric RAG queries.

    Used by agents to query the fabric database.
    """

    # From HENK1 handoff
    colors: Optional[list[str]] = Field(None, description="Preferred colors")
    patterns: Optional[list[str]] = Field(None, description="Preferred patterns")
    season: Optional[Season] = Field(None, description="Season requirement")
    occasion: Optional[str] = Field(
        None, description="Occasion (e.g., 'wedding', 'business')"
    )

    # Budget filtering
    budget_min: Optional[float] = Field(None, description="Min budget EUR")
    budget_max: Optional[float] = Field(None, description="Max budget EUR")

    # Feel/weight preferences
    weight_max: Optional[int] = Field(
        None,
        description="Maximalgewicht in g/m² (z. B. <260 für leichte Sommerstoffe)",
        gt=0,
    )
    preferred_materials: Optional[list[str]] = Field(
        None,
        description="Bevorzugte Materialien (z. B. Leinen, Baumwolle)",
    )

    # Stock requirement
    in_stock_only: bool = Field(default=True, description="Only show in-stock fabrics")

    # Limit results
    limit: int = Field(default=10, description="Max number of results", ge=1, le=50)


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


class FabricChunk(BaseModel):
    """
    Represents a chunk of fabric data for RAG processing.

    Used for vector embeddings and semantic search.
    """

    fabric_code: str = Field(..., description="Reference to fabric")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk text content")
    chunk_type: str = Field(
        ...,
        description="Type: 'characteristics', 'visual', 'usage', 'technical'",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional chunk metadata"
    )
    embedding: Optional[list[float]] = Field(
        None, description="Vector embedding (OpenAI)"
    )

    model_config = ConfigDict(use_enum_values=True)


class OutfitSpec(BaseModel):
    """
    Specification for outfit generation.

    Used by agents to request outfit visualizations.
    """

    occasion: str = Field(..., description="e.g., 'wedding', 'business', 'casual'")
    season: str = Field(..., description="e.g., 'summer', 'winter'")
    style_preferences: list[str] = Field(
        default_factory=list,
        description="e.g., ['classic', 'modern', 'bold']",
    )
    color_preferences: list[str] = Field(
        default_factory=list, description="Preferred colors"
    )
    pattern_preferences: list[str] = Field(
        default_factory=list, description="Preferred patterns"
    )
    fabric_codes: list[str] = Field(
        default_factory=list,
        description="Specific fabrics to use (if known)",
    )
    additional_notes: Optional[str] = Field(
        None, description="Additional requirements or notes"
    )

    model_config = ConfigDict(use_enum_values=True)


class GeneratedOutfit(BaseModel):
    """
    Result of DALL-E outfit generation.

    Contains generated image and metadata.
    """

    outfit_id: str = Field(..., description="Unique outfit identifier")
    spec: OutfitSpec = Field(..., description="Original specification")
    fabrics_used: list[str] = Field(
        default_factory=list, description="Fabric codes used"
    )
    dalle_prompt: str = Field(..., description="Prompt sent to DALL-E")
    image_url: Optional[str] = Field(None, description="Generated image URL")
    local_image_path: Optional[str] = Field(
        None, description="Local path to saved image"
    )
    revised_prompt: Optional[str] = Field(None, description="DALL-E's revised prompt")
    generation_date: Optional[str] = Field(
        None, description="ISO timestamp of generation"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    model_config = ConfigDict(use_enum_values=True)
