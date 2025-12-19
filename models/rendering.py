"""Structured models for fabric-first rendering pipeline."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class FabricImageURLs(BaseModel):
    """Image URLs for a fabric asset."""

    swatch: Optional[str] = None
    macro: Optional[str] = None
    extra: list[str] = Field(default_factory=list)


class FabricAsset(BaseModel):
    """Structured fabric asset selected for rendering."""

    fabric_id: str
    name: Optional[str] = None
    weaver: Optional[str] = None
    composition: Optional[str] = None
    weight_g: Optional[int] = None
    pattern: Optional[str] = None
    color: Optional[str] = None
    season: Optional[str] = None
    image_urls: FabricImageURLs


class JacketParameters(BaseModel):
    """Structured jacket configuration."""

    type: Literal["casual_jacket", "suit_jacket", "tuxedo"]
    lapel: Literal["notch", "peak", "shawl"]
    buttons: Literal["1", "2", "double_breasted"]
    fit: Optional[Literal["classic", "tailored", "slim"]] = None


class TrousersParameters(BaseModel):
    """Structured trousers configuration."""

    type: Literal["wool_trouser", "chino"]
    rise: Optional[Literal["low", "mid", "high"]] = None


class VestParameters(BaseModel):
    """Structured vest configuration."""

    enabled: bool = False


class ShirtParameters(BaseModel):
    """Structured shirt configuration."""

    collar: Optional[Literal["spread", "cutaway", "wing"]] = None
    color: Optional[str] = None


class NeckwearParameters(BaseModel):
    """Structured neckwear configuration."""

    type: Literal["tie", "bow_tie", "none"] = "tie"
    color: Optional[str] = None


class OutfitParameters(BaseModel):
    """Full outfit configuration."""

    jacket: JacketParameters
    trousers: TrousersParameters
    vest: VestParameters = Field(default_factory=VestParameters)
    shirt: ShirtParameters = Field(default_factory=ShirtParameters)
    neckwear: NeckwearParameters = Field(default_factory=NeckwearParameters)


class ProductParameters(BaseModel):
    """Top-level product parameters."""

    occasion: Optional[str] = None
    style_keywords: list[str] = Field(default_factory=list)
    outfit: OutfitParameters


RenderMode = Literal["product_sheet", "editorial", "catalog"]


class RenderRequest(BaseModel):
    """Render request for the fabric-first pipeline."""

    session_id: str
    fabric: FabricAsset
    params: ProductParameters
    mode: RenderMode = "product_sheet"
    size: Literal["1024x1024", "1024x1792", "1792x1024"] = "1024x1024"
    quality: Literal["standard", "hd"] = "standard"
    overlay_mode: Literal["bottom_strip", "side_card"] = "bottom_strip"
    overlay_height_ratio: float = 0.10


class RenderResult(BaseModel):
    """Result of a render run."""

    image_url: Optional[str]
    revised_prompt: Optional[str]
    success: bool
    local_path: Optional[str]
    error: Optional[str]
    used_params: ProductParameters
    used_fabric_id: str
    iteration: int


class JacketPatch(BaseModel):
    """Patch updates for jacket parameters."""

    type: Optional[Literal["casual_jacket", "suit_jacket", "tuxedo"]] = None
    lapel: Optional[Literal["notch", "peak", "shawl"]] = None
    buttons: Optional[Literal["1", "2", "double_breasted"]] = None
    fit: Optional[Literal["classic", "tailored", "slim"]] = None


class TrousersPatch(BaseModel):
    """Patch updates for trousers parameters."""

    type: Optional[Literal["wool_trouser", "chino"]] = None
    rise: Optional[Literal["low", "mid", "high"]] = None


class VestPatch(BaseModel):
    """Patch updates for vest parameters."""

    enabled: Optional[bool] = None


class ShirtPatch(BaseModel):
    """Patch updates for shirt parameters."""

    collar: Optional[Literal["spread", "cutaway", "wing"]] = None
    color: Optional[str] = None


class NeckwearPatch(BaseModel):
    """Patch updates for neckwear parameters."""

    type: Optional[Literal["tie", "bow_tie", "none"]] = None
    color: Optional[str] = None


class OutfitPatch(BaseModel):
    """Patch updates for the outfit."""

    jacket: Optional[JacketPatch] = None
    trousers: Optional[TrousersPatch] = None
    vest: Optional[VestPatch] = None
    shirt: Optional[ShirtPatch] = None
    neckwear: Optional[NeckwearPatch] = None


class ProductPatch(BaseModel):
    """Patch updates for product parameters."""

    occasion: Optional[str] = None
    style_keywords: Optional[list[str]] = None
    outfit: Optional[OutfitPatch] = None


class PatchDecision(BaseModel):
    """Decision describing how to update render parameters."""

    intent: Literal["update_render_params", "no_change", "clarify"]
    patch: Optional[ProductPatch] = None
    clarifying_question: Optional[str] = None
    notes_for_prompt: list[str] = Field(default_factory=list)
