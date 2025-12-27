"""API payload schemas for frontend contracts."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ImagePolicyDecision(BaseModel):
    """Decision describing how images may be used."""

    want_images: bool
    allowed_source: Literal["rag", "upload", "dalle", "none"]
    rationale: str = Field(..., min_length=3, max_length=240)
    required_fabric_images: bool
    max_images: int = Field(default=2, ge=0, le=6)
    block_reason: Optional[str] = None


class FabricRef(BaseModel):
    """Reference to a fabric used in responses."""

    fabric_id: Optional[str] = None
    fabric_code: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None
    pattern: Optional[str] = None
    composition: Optional[str] = None
    category: Optional[str] = None
    price_category: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    """Reference citation for RAG sources."""

    doc_id: str
    chunk_id: str
    score: float
    title: str


class ImagePayload(BaseModel):
    """Payload describing images returned to the frontend."""

    image_source: Literal["rag", "upload", "dalle", "none"]
    image_urls: list[str] = Field(default_factory=list)
