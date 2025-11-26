"""Tool Interface Models for RAG, CRM, DALLE, SAIA."""

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# RAG Database Tool Models
# ============================================================================


class RAGQuery(BaseModel):
    """Query for RAG database."""

    query: str = Field(..., description="Natural language query")
    customer_id: Optional[str] = None
    context_filter: Optional[dict] = Field(
        None, description="Additional filters (e.g., product category)"
    )
    top_k: int = Field(5, description="Number of results to return")


class RAGResult(BaseModel):
    """Result from RAG database query."""

    results: list[dict] = Field(
        default_factory=list, description="Retrieved documents/data"
    )
    metadata: Optional[dict] = None
    query_id: Optional[str] = None


# ============================================================================
# CRM (PIPEDRIVE) Tool Models
# ============================================================================


class CRMLeadCreate(BaseModel):
    """Create new lead in PIPEDRIVE."""

    customer_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: str = Field("initial_contact", description="Pipeline stage")
    source: str = Field("henk_bot", description="Lead source")
    notes: Optional[str] = None
    custom_fields: Optional[dict] = None


class CRMLeadUpdate(BaseModel):
    """Update existing lead in PIPEDRIVE."""

    lead_id: str
    stage: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: Optional[dict] = None
    status: Optional[str] = None


class CRMLeadResponse(BaseModel):
    """Response from CRM operations."""

    lead_id: str
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None


# ============================================================================
# DALLE Image Generation Tool Models
# ============================================================================


class DALLEImageRequest(BaseModel):
    """Request for DALLE image generation."""

    prompt: str = Field(..., description="Image generation prompt")
    style: str = Field(
        "natural", description="Style: 'natural' or 'vivid'"
    )
    size: str = Field("1024x1024", description="Image size")
    quality: str = Field("standard", description="'standard' or 'hd'")
    n: int = Field(1, description="Number of images")


class DALLEImageResponse(BaseModel):
    """Response from DALLE image generation."""

    image_url: str
    revised_prompt: Optional[str] = Field(
        None, description="DALLE revised prompt"
    )
    success: bool = True
    error: Optional[str] = None


# ============================================================================
# SAIA 3D Measurement Tool Models
# ============================================================================


class SAIAMeasurementRequest(BaseModel):
    """Request for SAIA 3D measurement."""

    customer_id: str
    scan_type: str = Field("full_body", description="Type of 3D scan")
    appointment_id: Optional[str] = Field(
        None, description="If scheduled measurement"
    )


class SAIAMeasurementResponse(BaseModel):
    """Response from SAIA 3D measurement."""

    measurement_id: str
    success: bool
    measurements: Optional[dict] = Field(
        None, description="Parsed measurement data"
    )
    raw_scan_url: Optional[str] = Field(
        None, description="URL to raw scan data"
    )
    error: Optional[str] = None
