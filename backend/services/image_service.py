from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:  # pragma: no cover - optional PIL dependency
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - environment without Pillow
    Image = ImageDraw = ImageFont = None

from backend.prompts.loader import PromptLoader
from backend.settings import get_settings
from models.api_payload import ImagePolicyDecision
from models.rendering import RenderRequest, RenderResult
from models.tools import DALLEImageRequest, DALLEImageResponse

from .image_providers.base import ImageProvider
from .image_providers.dalle_provider import DalleProvider
from .image_providers.imagen_provider import ImagenProvider

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(self, provider: ImageProvider, prompt_loader: PromptLoader | None = None):
        self.provider = provider
        self.prompt_loader = prompt_loader or PromptLoader()
        # Align with Flask static route /static/generated_images served from project root
        self.images_dir = Path(__file__).resolve().parent.parent.parent / "generated_images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------- public API ---------------------------
    async def generate_image(
        self, request: DALLEImageRequest, decision: Optional[ImagePolicyDecision] = None
    ) -> DALLEImageResponse:
        policy_block = self._policy_blocked(decision)
        if policy_block:
            return policy_block

        try:
            image_bytes = await self.provider.generate(
                request.prompt,
                size=request.size,
                quality=request.quality,
                n=request.n,
            )
        except Exception as exc:
            logger.error("[ImageService] Generation failed: %s", exc, exc_info=True)
            return DALLEImageResponse(
                image_url=None,
                revised_prompt=getattr(self.provider, "last_revised_prompt", None),
                success=False,
                error=str(exc),
            )

        filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        local_path = self.images_dir / filename
        local_path.write_bytes(image_bytes[0])
        image_url = f"/static/generated_images/{filename}"

        return DALLEImageResponse(
            image_url=image_url,
            local_path=str(local_path),
            revised_prompt=getattr(self.provider, "last_revised_prompt", None),
            success=True,
        )

    async def generate_mood_board_with_fabrics(
        self,
        fabrics: List[Dict[str, Any]],
        occasion: str,
        style_keywords: Optional[List[str]] = None,
        design_preferences: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        decision: Optional[ImagePolicyDecision] = None,
    ) -> DALLEImageResponse:
        policy_block = self._policy_blocked(decision)
        if policy_block:
            return policy_block

        if not fabrics:
            return DALLEImageResponse(
                image_url=None,
                revised_prompt="No fabrics available",
                success=False,
                error="No fabrics provided",
            )

        prompt = self._build_mood_board_prompt(
            fabrics[:2], occasion, style_keywords=style_keywords, design_preferences=design_preferences
        )

        generation = await self.generate_image(
            DALLEImageRequest(prompt=prompt, size="1024x1024", quality="standard"),
            decision=decision,
        )
        if not generation.success or not generation.local_path:
            return generation

        if Image is None:
            logger.warning("[ImageService] Pillow missing; returning generated image without composite")
            return generation

        try:
            mood_board_img = Image.open(generation.local_path)
        except Exception as exc:
            logger.error("[ImageService] Failed to load generated image: %s", exc)
            return generation

        try:
            composite_img = self._create_composite_with_fabric_thumbnails(mood_board_img, fabrics[:2])
            filename = f"mood_board_composite_{session_id or 'temp'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            composite_path = self.images_dir / filename
            composite_img.save(composite_path, format="PNG", quality=95)
            composite_url = f"/static/generated_images/{filename}"
            return DALLEImageResponse(
                image_url=composite_url,
                local_path=str(composite_path),
                revised_prompt=generation.revised_prompt,
                success=True,
            )
        except Exception as exc:
            logger.error("[ImageService] Failed to create composite: %s", exc, exc_info=True)
            return generation

    async def generate_product_sheet(
        self,
        request: RenderRequest,
        notes_for_prompt: Optional[list[str]] = None,
        decision: Optional[ImagePolicyDecision] = None,
    ) -> RenderResult:
        policy_block = self._policy_blocked(decision)
        if policy_block:
            return RenderResult(
                image_url=None,
                revised_prompt=None,
                success=False,
                local_path=None,
                error=policy_block.policy_reason,
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

        if Image is None:
            return RenderResult(
                image_url=None,
                revised_prompt=None,
                success=False,
                local_path=None,
                error="Pillow is required for fabric overlays but is not installed.",
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

        fabric_image_url = self._select_fabric_image(request)
        if not fabric_image_url:
            return RenderResult(
                image_url=None,
                revised_prompt=None,
                success=False,
                local_path=None,
                error="No fabric image available for overlay.",
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

        prompt = self._build_product_sheet_prompt(request, notes_for_prompt or [])
        generation = await self.generate_image(
            DALLEImageRequest(prompt=prompt, size=request.size, quality=request.quality),
            decision=decision,
        )
        if not generation.success or not generation.local_path:
            return RenderResult(
                image_url=generation.image_url,
                revised_prompt=generation.revised_prompt,
                success=False,
                local_path=generation.local_path,
                error=generation.error,
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

        try:
            base_image = Image.open(generation.local_path)
            fabric_image = self._download_image(fabric_image_url)
            composite = self._create_product_sheet_overlay(
                base_image, fabric_image, request.overlay_mode, request.overlay_height_ratio
            )
            filename = f"product_sheet_{request.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            composite_path = self.images_dir / filename
            composite.save(composite_path, format="PNG", quality=95)
            composite_url = f"/static/generated_images/{filename}"
            return RenderResult(
                image_url=composite_url,
                revised_prompt=generation.revised_prompt,
                success=True,
                local_path=str(composite_path),
                error=None,
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )
        except Exception as exc:
            logger.error("[ImageService] Failed to build product sheet composite", exc_info=exc)
            return RenderResult(
                image_url=generation.image_url,
                revised_prompt=generation.revised_prompt,
                success=False,
                local_path=generation.local_path,
                error=str(exc),
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

    # --------------------------- prompt builders ---------------------------
    def _build_mood_board_prompt(
        self,
        fabrics: List[Dict[str, Any]],
        occasion: str,
        style_keywords: Optional[List[str]] = None,
        design_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        variables = self._build_moodboard_variables(fabrics, occasion, style_keywords, design_preferences)
        return self.prompt_loader.render_template("moodboard_sportjacket.md", variables)

    def _build_product_sheet_prompt(self, request: RenderRequest, notes_for_prompt: list[str]) -> str:
        params = request.params
        outfit = params.outfit
        notes_text = "\n".join(f"- {note}" for note in notes_for_prompt) if notes_for_prompt else ""
        variables = {
            "outfit": {
                "jacket": f"{outfit.jacket.type} lapel {outfit.jacket.lapel} buttons {outfit.jacket.buttons}",
                "trousers": f"{outfit.trousers.type} rise {outfit.trousers.rise or 'mid'}",
                "vest": "included" if outfit.vest.enabled else "not included",
                "shirt": f"{outfit.shirt.collar or 'spread'} collar, {outfit.shirt.color or 'white'}",
                "neckwear": f"{outfit.neckwear.type} {outfit.neckwear.color or ''}",
            },
            "params": {"occasion": params.occasion or "formal"},
            "style_keywords": ", ".join(params.style_keywords) if params.style_keywords else "minimal, refined",
            "fabric_color": request.fabric.color or "classic tone",
            "fabric_pattern": request.fabric.pattern or "solid",
            "fabric_composition": request.fabric.composition or "fine wool",
            "notes_text": notes_text,
        }
        return self.prompt_loader.render_template("product_sheet.md", variables)

    # --------------------------- helpers ---------------------------
    def _build_moodboard_variables(
        self,
        fabrics: List[Dict[str, Any]],
        occasion: str,
        style_keywords: Optional[List[str]],
        design_preferences: Optional[Dict[str, Any]],
    ) -> dict[str, Any]:
        occasion_scenes = {
            "Hochzeit": "elegant wedding reception venue with soft natural lighting, romantic garden setting",
            "Business": "modern executive office with floor-to-ceiling windows, professional corporate environment",
            "Gala": "luxury ballroom with chandeliers, sophisticated evening event atmosphere",
            "Casual": "contemporary urban lifestyle setting, natural daylight",
        }
        scene = occasion_scenes.get(occasion, "elegant professional setting")
        style_kw = ", ".join(style_keywords) if style_keywords else "timeless elegant"

        fabric_context_lines = []
        fabric_image = ""
        for fabric in fabrics[:4]:
            color = fabric.get("color", "classic")
            pattern = fabric.get("pattern", "solid")
            composition = fabric.get("composition", "fine wool")
            fabric_code = fabric.get("fabric_code") or "N/A"
            weight = fabric.get("weight_g_m2") or fabric.get("weight")
            category = fabric.get("category") or "unspecified"
            fabric_context_lines.append(
                f"- {fabric_code}: color={color}, pattern={pattern}, composition={composition}, "
                f"category={category}, weight={weight or 'n/a'}"
            )
            if not fabric_image:
                fabric_image = fabric.get("image_url") or fabric.get("url") or ""

        fabric_context_block = "\n".join(fabric_context_lines)

        design_details_parts: list[str] = []
        vest_instruction = ""
        trouser_color_instruction = ""
        material_requirement = ""
        constraints_summary_lines: list[str] = []
        garments_lines: list[str] = []
        jacket_front = shoulder = lapel_style = ""
        shirt = neckwear = ""
        if design_preferences:
            revers = design_preferences.get("revers_type", "")
            shoulder = design_preferences.get("shoulder_padding", "")
            waistband = design_preferences.get("waistband_type", "")
            jacket_front = design_preferences.get("jacket_front", "")
            lapel_style = design_preferences.get("lapel_style", "")
            lapel_roll = design_preferences.get("lapel_roll", "")
            trouser_front = design_preferences.get("trouser_front", "")
            wants_vest = design_preferences.get("wants_vest")
            trouser_color = design_preferences.get("trouser_color")
            preferred_material = design_preferences.get("preferred_material")
            requested_fabric_code = design_preferences.get("requested_fabric_code")
            shirt = design_preferences.get("shirt") or "NONE"
            neckwear = design_preferences.get("neckwear") or "NONE"

            if jacket_front:
                if jacket_front == "single_breasted":
                    design_details_parts.append("Single-breasted jacket (one row of buttons)")
                elif jacket_front == "double_breasted":
                    design_details_parts.append("Double-breasted jacket (two rows of buttons)")

            lapel_parts = []
            if lapel_style:
                lapel_mapping = {
                    "peak": "peak lapels (pointed upward)",
                    "notch": "notch lapels (standard notch)",
                    "shawl": "shawl collar",
                }
                lapel_parts.append(lapel_mapping.get(lapel_style, lapel_style))
            if lapel_roll:
                if lapel_roll == "rolling":
                    lapel_parts.append("with soft rolling/falling lapels")
                elif lapel_roll == "flat":
                    lapel_parts.append("with flat lapels")
            if lapel_parts:
                design_details_parts.append(" ".join(lapel_parts))
            elif revers:
                design_details_parts.append(f"{revers} lapels")

            if shoulder:
                shoulder_mapping = {
                    "none": "unstructured soft shoulders (spalla camicia, no padding)",
                    "light": "lightly padded shoulders",
                    "medium": "medium shoulder padding",
                    "structured": "structured shoulders with strong padding",
                }
                design_details_parts.append(shoulder_mapping.get(shoulder, f"{shoulder} shoulders"))

            trouser_parts = []
            if trouser_front:
                if trouser_front == "pleats":
                    trouser_parts.append("pleated front trousers")
                elif trouser_front == "flat_front":
                    trouser_parts.append("flat front trousers")
            elif waistband:
                trouser_parts.append(f"{waistband} trousers")
            if trouser_parts:
                design_details_parts.append(", ".join(trouser_parts))

            if trouser_color := design_preferences.get("trouser_color"):
                trouser_color_label = str(trouser_color).replace("_", " ")
                trouser_color_instruction = (
                    f"TROUSERS COLOR: {trouser_color_label} (contrast trousers; jacket remains in fabric tone)"
                )

            if design_details_parts:
                design_details = "- " + "\n- ".join(design_details_parts)
            else:
                design_details = ""

            if wants_vest is False:
                vest_instruction = (
                    "CRITICAL COMPOSITION: Show TWO-PIECE suit ONLY (jacket and trousers). "
                    "NOT a three-piece. NO vest/waistcoat/gilet visible. Absolutely exclude any vest."
                )
            elif wants_vest is True:
                vest_instruction = (
                    "CRITICAL COMPOSITION: Show THREE-PIECE suit (jacket, matching vest/waistcoat, and trousers). "
                    "Vest must be visible under the jacket."
                )

            if preferred_material:
                material_requirement = preferred_material

            constraints_summary_lines = [
                f"- occasion={occasion}" if occasion else None,
                f"- jacket_front={jacket_front}" if jacket_front else None,
                f"- shoulder={shoulder}" if shoulder else None,
                f"- lapel_style={lapel_style}" if lapel_style else None,
                f"- waist={waistband}" if waistband else None,
                f"- trouser_color={trouser_color}" if design_preferences.get("trouser_color") else None,
                f"- requested_fabric_code={requested_fabric_code}" if requested_fabric_code else None,
            ]
            garments_lines = [
                f"- Jacket: {jacket_front or 'tailored'} front",
                f"- Shoulders: {shoulder or 'classic'}",
                f"- Lapel: {lapel_style or 'notch'}",
                f"- Trouser front: {trouser_front or waistband or 'clean'}",
            ]
        else:
            design_details = ""
            garments_lines = ["- Tailored jacket", "- Coordinated trousers"]
            trouser_color = ""
            vest_instruction = ""

        constraints_summary_block = "\n".join([line for line in constraints_summary_lines if line])
        garments_block = "\n".join(garments_lines)

        return {
            "fabric_context_block": fabric_context_block,
            "fabric_image": fabric_image,
            "occasion": occasion,
            "garments_block": garments_block,
            "jacket_front": jacket_front,
            "shoulder": shoulder,
            "lapel_style_or_revers": lapel_style,
            "wants_vest_text": "with vest" if design_preferences and design_preferences.get("wants_vest") else "",
            "trouser_color": design_preferences.get("trouser_color") if design_preferences else "",
            "shirt": shirt or "NONE",
            "neckwear": neckwear or "NONE",
            "material_requirement": material_requirement,
            "design_details": design_details,
            "trouser_color_instruction": trouser_color_instruction,
            "vest_instruction": vest_instruction,
            "constraints_summary_block": constraints_summary_block,
            "style_keywords": style_kw,
            "scene": scene,
        }

    def _select_fabric_image(self, request: RenderRequest) -> Optional[str]:
        image_urls = request.fabric.image_urls
        return image_urls.swatch or image_urls.macro or (image_urls.extra[0] if image_urls.extra else None)

    def _policy_blocked(self, decision: Optional[ImagePolicyDecision]) -> Optional[DALLEImageResponse]:
        if decision and decision.allowed_source and decision.allowed_source != self.provider.name:
            return DALLEImageResponse(
                image_url=None,
                revised_prompt=None,
                success=False,
                error="Image generation blocked by policy.",
                policy_blocked=True,
                policy_reason=decision.block_reason or decision.rationale,
            )
        return None

    def _download_image(self, url: str):
        if Image is None:
            raise RuntimeError("Pillow not installed; cannot download images")

        if url.startswith("/fabrics/"):
            project_root = Path(__file__).resolve().parents[2]
            local_path = project_root / "storage" / url.lstrip("/")
            if local_path.exists():
                logger.info("[ImageService] Loading fabric image from local path: %s", local_path)
                return Image.open(local_path)
            raise FileNotFoundError(f"Fabric image not found: {local_path}")

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))

    def _create_composite_with_fabric_thumbnails(
        self, mood_board: Image.Image, fabrics: List[Dict[str, Any]]
    ) -> Image.Image:
        if Image is None:
            raise RuntimeError("Pillow not installed; cannot compose images")

        mb_width, mb_height = mood_board.size
        thumb_width = int(mb_width * 0.2)
        thumb_height = int(mb_height * 0.2)

        fabric_thumbnails = []
        for fabric in fabrics[:2]:
            image_url = fabric.get("image_url") or fabric.get("image") or fabric.get("url")
            if not image_url:
                continue
            try:
                fabric_img = self._download_image(image_url)
                fabric_img.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                fabric_thumbnails.append(
                    {
                        "image": fabric_img,
                        "fabric_code": fabric.get("fabric_code", ""),
                        "name": fabric.get("name", ""),
                    }
                )
            except Exception as exc:
                logger.warning("[ImageService] Failed to download fabric image: %s", exc)
                continue

        if not fabric_thumbnails:
            logger.info("[ImageService] No fabric thumbnails available, returning original mood board")
            return mood_board

        composite = mood_board.copy()
        draw = ImageDraw.Draw(composite)
        padding = 20
        x_offset = mb_width - thumb_width - padding
        y_offset = mb_height - (thumb_height * len(fabric_thumbnails)) - (padding * len(fabric_thumbnails))

        for i, thumb_data in enumerate(fabric_thumbnails):
            thumb_img = thumb_data["image"]
            fabric_code = thumb_data["fabric_code"]
            x = x_offset
            y = y_offset + (i * (thumb_height + padding))
            box_padding = 5
            draw.rectangle(
                [
                    x - box_padding,
                    y - box_padding,
                    x + thumb_width + box_padding,
                    y + thumb_height + box_padding + 20,
                ],
                fill="white",
                outline="black",
                width=2,
            )
            composite.paste(thumb_img, (x, y))
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12
                )
            except Exception:
                font = ImageFont.load_default()
            text_y = y + thumb_height + 2
            draw.text((x, text_y), f"Ref: {fabric_code}", fill="black", font=font)

        logger.info("[ImageService] Added %d fabric thumbnails to mood board", len(fabric_thumbnails))
        return composite

    def _create_product_sheet_overlay(
        self,
        base_image: Image.Image,
        fabric_image: Image.Image,
        overlay_mode: str,
        overlay_height_ratio: float,
    ) -> Image.Image:
        if Image is None:
            raise RuntimeError("Pillow not installed; cannot create overlays")

        base = base_image.convert("RGB")
        fabric = fabric_image.convert("RGB")
        width, height = base.size
        overlay_height = max(1, int(height * overlay_height_ratio))

        if overlay_mode == "side_card":
            card_width = int(width * 0.22)
            card_height = int(height * 0.30)
            card_x = width - card_width - int(width * 0.04)
            card_y = int((height - card_height) / 2)

            card = Image.new("RGB", (card_width, card_height), "white")
            padding = int(card_width * 0.08)
            target_w = card_width - 2 * padding
            target_h = card_height - 2 * padding
            fabric.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            fabric_x = padding + int((target_w - fabric.width) / 2)
            fabric_y = padding + int((target_h - fabric.height) / 2)
            card.paste(fabric, (fabric_x, fabric_y))

            composite = base.copy()
            composite.paste(card, (card_x, card_y))
            return composite

        strip = Image.new("RGB", (width, overlay_height), "white")
        padding = max(4, int(overlay_height * 0.08))
        target_height = overlay_height - 2 * padding
        target_width = width - 2 * padding
        fabric.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        fabric_x = padding + int((target_width - fabric.width) / 2)
        fabric_y = padding + int((target_height - fabric.height) / 2)
        strip.paste(fabric, (fabric_x, fabric_y))

        composite = base.copy()
        composite.paste(strip, (0, height - overlay_height))
        return composite


def _select_provider() -> ImageProvider:
    settings = get_settings()
    provider_name = settings.image_provider

    if provider_name in {"imagen", "auto"}:
        imagen = ImagenProvider(
            project=settings.gcp_project,
            location=settings.gcp_location,
            model=settings.imagen_model,
            credentials_path=settings.credentials_path,
            credentials_json=settings.credentials_json,
        )
        if settings.imagen_ready() and imagen.credentials:
            return imagen
        logger.warning(
            "[ImageService] Imagen unavailable, falling back to OpenAI/DALL·E"
        )
        if provider_name == "imagen":
            logger.info("[ImageService] Setze DALL·E als Fallback, weil Imagen-Konfiguration fehlt")
    return DalleProvider()


_image_service: Optional[ImageService] = None


def get_image_service() -> ImageService:
    global _image_service
    if _image_service is None:
        provider = _select_provider()
        _image_service = ImageService(provider=provider)
        logger.info("[ImageService] Singleton instance created with provider=%s", provider.name)
    return _image_service
