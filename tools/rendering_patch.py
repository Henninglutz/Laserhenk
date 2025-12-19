"""Apply structured patches to product parameters."""

from __future__ import annotations

from models.rendering import (
    JacketPatch,
    NeckwearPatch,
    OutfitParameters,
    OutfitPatch,
    ProductParameters,
    ProductPatch,
    ShirtPatch,
    TrousersPatch,
    VestPatch,
)


def _apply_jacket_patch(target: OutfitParameters, patch: JacketPatch) -> None:
    if patch.type is not None:
        target.jacket.type = patch.type
    if patch.lapel is not None:
        target.jacket.lapel = patch.lapel
    if patch.buttons is not None:
        target.jacket.buttons = patch.buttons
    if patch.fit is not None:
        target.jacket.fit = patch.fit


def _apply_trousers_patch(target: OutfitParameters, patch: TrousersPatch) -> None:
    if patch.type is not None:
        target.trousers.type = patch.type
    if patch.rise is not None:
        target.trousers.rise = patch.rise


def _apply_vest_patch(target: OutfitParameters, patch: VestPatch) -> None:
    if patch.enabled is not None:
        target.vest.enabled = patch.enabled


def _apply_shirt_patch(target: OutfitParameters, patch: ShirtPatch) -> None:
    if patch.collar is not None:
        target.shirt.collar = patch.collar
    if patch.color is not None:
        target.shirt.color = patch.color


def _apply_neckwear_patch(target: OutfitParameters, patch: NeckwearPatch) -> None:
    if patch.type is not None:
        target.neckwear.type = patch.type
    if patch.color is not None:
        target.neckwear.color = patch.color


def _apply_outfit_patch(target: OutfitParameters, patch: OutfitPatch) -> None:
    if patch.jacket is not None:
        _apply_jacket_patch(target, patch.jacket)
    if patch.trousers is not None:
        _apply_trousers_patch(target, patch.trousers)
    if patch.vest is not None:
        _apply_vest_patch(target, patch.vest)
    if patch.shirt is not None:
        _apply_shirt_patch(target, patch.shirt)
    if patch.neckwear is not None:
        _apply_neckwear_patch(target, patch.neckwear)


def apply_patch(params: ProductParameters, patch: ProductPatch) -> ProductParameters:
    """
    Apply a patch to product parameters.

    Rules:
    - Only update provided fields (None means no change).
    - Never drop sub-objects.
    """
    updated = params.model_copy(deep=True)

    if patch.occasion is not None:
        updated.occasion = patch.occasion
    if patch.style_keywords is not None:
        updated.style_keywords = list(patch.style_keywords)
    if patch.outfit is not None:
        _apply_outfit_patch(updated.outfit, patch.outfit)

    return updated
