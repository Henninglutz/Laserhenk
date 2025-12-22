"""DALLE Tool - Image Generation with Fabric Reference Compositing."""

from __future__ import annotations

import logging
import os
import io
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import requests

try:  # Optional dependency; falls back gracefully when unavailable
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - environment without Pillow
    Image = ImageDraw = ImageFont = None

from openai import AsyncOpenAI

from models.api_payload import ImagePolicyDecision
from models.rendering import RenderRequest, RenderResult
from models.tools import DALLEImageRequest, DALLEImageResponse

logger = logging.getLogger(__name__)


class DALLETool:
    """
    DALLE Image Generation Tool with Fabric Reference Compositing.

    Features:
    - DALL-E 3 API integration
    - Mood board generation with fabric descriptions
    - Composite images: DALL-E mood board + real fabric thumbnails
    - Local image caching
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DALLE Tool.

        Args:
            api_key: OpenAI API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.enabled = os.getenv("ENABLE_DALLE", "true").lower() == "true"
        self.images_dir = Path(__file__).parent.parent / "generated_images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        if Image is None:
            logger.warning(
                "[DALLETool] Pillow not installed; skipping composite image features"
            )

        if not self.client:
            logger.warning("[DALLETool] OpenAI API key not set, DALL-E disabled")
            self.enabled = False

    def _policy_blocked(self, decision: Optional[ImagePolicyDecision]) -> Optional[DALLEImageResponse]:
        if decision and decision.allowed_source != "dalle":
            return DALLEImageResponse(
                image_url=None,
                revised_prompt=None,
                success=False,
                error="Image policy blocked DALL-E generation.",
                policy_blocked=True,
                policy_reason=decision.block_reason or decision.rationale,
            )
        return None

    async def generate_image(
        self,
        request: DALLEImageRequest,
        decision: Optional[ImagePolicyDecision] = None,
    ) -> DALLEImageResponse:
        """
        Generate image with DALL-E 3.

        Args:
            request: Image generation parameters

        Returns:
            Generated image response
        """
        policy_block = self._policy_blocked(decision)
        if policy_block:
            return policy_block

        if not self.enabled:
            return DALLEImageResponse(
                image_url=None,
                revised_prompt=request.prompt,
                success=False,
                error="DALL-E is disabled (missing API key or ENABLE_DALLE=false)",
            )

        try:
            logger.info(f"[DALLETool] Generating image: {request.prompt[:100]}...")

            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=request.prompt,
                size=request.size or "1024x1024",
                quality=request.quality or "standard",
                n=1,
            )

            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt

            logger.info(f"[DALLETool] Image generated: {image_url}")

            return DALLEImageResponse(
                image_url=image_url,
                revised_prompt=revised_prompt,
                success=True,
            )

        except Exception as e:
            logger.error(f"[DALLETool] Error generating image: {e}", exc_info=True)
            return DALLEImageResponse(
                image_url=None,
                revised_prompt=request.prompt,
                success=False,
                error=str(e),
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
        """
        Generate mood board with real fabric thumbnails as reference.

        IMPORTANT: Creates composite image:
        1. DALL-E generates mood board based on fabric descriptions + occasion + design details
        2. Real fabric photos are added as small thumbnails (10% size, bottom right/left)

        Args:
            fabrics: List of fabric data dicts (from rag_context)
            occasion: Occasion/setting (e.g., "Hochzeit", "Business")
            style_keywords: Optional style keywords
            design_preferences: Optional design details (revers_type, shoulder_padding, waistband_type)
            session_id: Optional session ID for caching

        Returns:
            Composite image with mood board + fabric thumbnails
        """
        policy_block = self._policy_blocked(decision)
        if policy_block:
            return policy_block

        if not fabrics or len(fabrics) == 0:
            logger.warning("[DALLETool] No fabrics provided for mood board")
            return DALLEImageResponse(
                image_url=None,
                revised_prompt="No fabrics available",
                success=False,
                error="No fabrics provided",
            )

        # Build detailed prompt with fabric descriptions and design details
        prompt = self._build_mood_board_prompt(fabrics[:2], occasion, style_keywords, design_preferences)

        # Generate mood board with DALL-E
        dalle_response = await self.generate_image(
            DALLEImageRequest(
                prompt=prompt,
                size="1024x1024",
                quality="standard",
            ),
            decision=decision,
        )

        if not dalle_response.success or not dalle_response.image_url:
            return dalle_response

        if Image is None:
            logger.warning("[DALLETool] Pillow missing; returning raw DALL-E image")
            return dalle_response

        # Download DALL-E image
        try:
            mood_board_img = self._download_image(dalle_response.image_url)
        except Exception as e:
            logger.error(f"[DALLETool] Failed to download DALL-E image: {e}")
            return dalle_response  # Return original without composite

        # Create composite with fabric thumbnails
        try:
            composite_img = self._create_composite_with_fabric_thumbnails(
                mood_board_img, fabrics[:2]
            )

            # Save composite image
            filename = f"mood_board_composite_{session_id or 'temp'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            composite_path = self.images_dir / filename
            composite_img.save(composite_path, format="PNG", quality=95)

            # Convert to web-accessible URL (assuming static file serving)
            # TODO: Configure proper static URL mapping
            composite_url = f"/static/generated_images/{filename}"

            logger.info(f"[DALLETool] Composite image created: {composite_path}")

            return DALLEImageResponse(
                image_url=composite_url,
                local_path=str(composite_path),
                revised_prompt=dalle_response.revised_prompt,
                success=True,
            )

        except Exception as e:
            logger.error(f"[DALLETool] Failed to create composite: {e}", exc_info=True)
            # Return original DALL-E image as fallback
            return dalle_response

    def _build_mood_board_prompt(
        self,
        fabrics: List[Dict[str, Any]],
        occasion: str,
        style_keywords: Optional[List[str]] = None,
        design_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build DALL-E prompt for mood board with fabric descriptions and design details.

        Args:
            fabrics: Top 2 fabrics from RAG
            occasion: Occasion/setting
            style_keywords: Style keywords
            design_preferences: Design details (revers_type, shoulder_padding, waistband_type)

        Returns:
            Detailed DALL-E prompt
        """
        # Base scene based on occasion
        occasion_scenes = {
            "Hochzeit": "elegant wedding reception venue with soft natural lighting, romantic garden setting",
            "Business": "modern executive office with floor-to-ceiling windows, professional corporate environment",
            "Gala": "luxury ballroom with chandeliers, sophisticated evening event atmosphere",
            "Casual": "contemporary urban lifestyle setting, natural daylight",
        }

        scene = occasion_scenes.get(occasion, "elegant professional setting")
        style = ", ".join(style_keywords) if style_keywords else "timeless elegant"

        # Fabric descriptions
        fabric_descriptions = []
        for i, fabric in enumerate(fabrics[:2], 1):
            color = fabric.get("color", "classic")
            pattern = fabric.get("pattern", "solid")
            composition = fabric.get("composition", "fine wool")

            fabric_desc = f"{color} {pattern} fabric in {composition}"
            fabric_descriptions.append(fabric_desc)

        fabrics_text = " and ".join(fabric_descriptions)

        # Extract design preferences if provided
        design_details = ""
        vest_instruction = ""
        if design_preferences:
            revers = design_preferences.get("revers_type", "")
            shoulder = design_preferences.get("shoulder_padding", "")
            waistband = design_preferences.get("waistband_type", "")
            jacket_front = design_preferences.get("jacket_front", "")
            lapel_style = design_preferences.get("lapel_style", "")
            lapel_roll = design_preferences.get("lapel_roll", "")
            trouser_front = design_preferences.get("trouser_front", "")
            wants_vest = design_preferences.get("wants_vest")

            # Build comprehensive design details
            design_details_parts = []

            # Jacket construction
            if jacket_front:
                if jacket_front == "single_breasted":
                    design_details_parts.append("Single-breasted jacket (one row of buttons)")
                elif jacket_front == "double_breasted":
                    design_details_parts.append("Double-breasted jacket (two rows of buttons)")

            # Lapel styling
            lapel_parts = []
            if lapel_style:
                lapel_mapping = {
                    "peak": "peak lapels (pointed upward)",
                    "notch": "notch lapels (standard notch)",
                    "shawl": "shawl collar"
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

            # Shoulder construction
            if shoulder:
                shoulder_mapping = {
                    "none": "unstructured soft shoulders (spalla camicia, no padding)",
                    "light": "lightly padded shoulders",
                    "medium": "medium shoulder padding",
                    "structured": "structured shoulders with strong padding"
                }
                design_details_parts.append(shoulder_mapping.get(shoulder, f"{shoulder} shoulders"))

            # Trouser details
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

            if design_details_parts:
                design_details = "\n\nSUIT DESIGN SPECIFICATIONS:\n- " + "\n- ".join(design_details_parts)

            # Add explicit vest instruction
            if wants_vest is False:
                vest_instruction = "\n\nCRITICAL COMPOSITION: Show TWO-PIECE suit ONLY (jacket and trousers). NO vest/waistcoat visible. Two-piece configuration."
                logger.info("[DALLETool] Adding NO VEST instruction to prompt")
            elif wants_vest is True:
                vest_instruction = "\n\nCRITICAL COMPOSITION: Show THREE-PIECE suit (jacket, matching vest/waistcoat, and trousers). Vest must be visible under the jacket."
                logger.info("[DALLETool] Adding WITH VEST instruction to prompt")
            else:
                logger.info(f"[DALLETool] No vest preference set (wants_vest={wants_vest})")

        # Build final prompt
        design_pref_summary = []
        if design_preferences:
            if design_preferences.get("jacket_front"):
                design_pref_summary.append(f"jacket_front={design_preferences['jacket_front']}")
            if design_preferences.get("lapel_style"):
                design_pref_summary.append(f"lapel_style={design_preferences['lapel_style']}")
            if design_preferences.get("lapel_roll"):
                design_pref_summary.append(f"lapel_roll={design_preferences['lapel_roll']}")
            if design_preferences.get("shoulder_padding"):
                design_pref_summary.append(f"shoulder={design_preferences['shoulder_padding']}")
            if design_preferences.get("trouser_front"):
                design_pref_summary.append(f"trouser={design_preferences['trouser_front']}")

        logger.info(
            "[DALLETool] Building prompt with design prefs: %s, vest_instruction=%d chars",
            ", ".join(design_pref_summary) if design_pref_summary else "none",
            len(vest_instruction),
        )

        prompt = f"""Create an elegant mood board for a bespoke men's suit in a {scene}.

FABRIC REFERENCE:
Use these fabrics only as color/pattern inspiration (do NOT replicate exact fabric patterns).{design_details}{vest_instruction}

STYLE DIRECTION:
{style}, sophisticated, high-quality menswear photography.

VISUAL REQUIREMENTS:
- Professional fashion editorial style with clean layout
- Luxurious atmosphere with attention to tailoring details
- Show the suit clearly with proper fit and drape
- Natural lighting that highlights fabric texture and construction

SETTING:
{occasion} - create the appropriate ambiance and backdrop.

CRITICAL INSTRUCTIONS:
- Realistic photograph ONLY - NOT illustration, NOT drawing, NOT sketch
- High-quality professional photography with photorealistic details
- Ensure all design specifications are clearly visible
- Leave bottom-right corner visually calm (for fabric swatch overlay)"""

        logger.info(f"[DALLETool] Generated prompt ({len(prompt)} chars): {prompt[:200]}...")
        return prompt

    async def generate_product_sheet(
        self,
        request: RenderRequest,
        notes_for_prompt: Optional[list[str]] = None,
        decision: Optional[ImagePolicyDecision] = None,
    ) -> RenderResult:
        """
        Generate a product sheet render with a real fabric overlay.

        The output always includes a real fabric reference image as an overlay.
        """
        if decision and decision.allowed_source != "dalle":
            return RenderResult(
                image_url=None,
                revised_prompt=None,
                success=False,
                local_path=None,
                error=decision.block_reason or decision.rationale,
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
        dalle_response = await self.generate_image(
            DALLEImageRequest(
                prompt=prompt,
                size=request.size,
                quality=request.quality,
            ),
            decision=decision,
        )

        if not dalle_response.success or not dalle_response.image_url:
            return RenderResult(
                image_url=dalle_response.image_url,
                revised_prompt=dalle_response.revised_prompt,
                success=False,
                local_path=dalle_response.local_path,
                error=dalle_response.error,
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

        try:
            base_image = self._download_image(dalle_response.image_url)
            fabric_image = self._download_image(fabric_image_url)
            composite = self._create_product_sheet_overlay(
                base_image,
                fabric_image,
                request.overlay_mode,
                request.overlay_height_ratio,
            )
            filename = (
                f"product_sheet_{request.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            composite_path = self.images_dir / filename
            composite.save(composite_path, format="PNG", quality=95)
            composite_url = f"/static/generated_images/{filename}"
            return RenderResult(
                image_url=composite_url,
                revised_prompt=dalle_response.revised_prompt,
                success=True,
                local_path=str(composite_path),
                error=None,
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )
        except Exception as exc:
            logger.error("[DALLETool] Failed to build product sheet composite", exc_info=exc)
            return RenderResult(
                image_url=dalle_response.image_url,
                revised_prompt=dalle_response.revised_prompt,
                success=False,
                local_path=dalle_response.local_path,
                error=str(exc),
                used_params=request.params,
                used_fabric_id=request.fabric.fabric_id,
                iteration=0,
            )

    def _select_fabric_image(self, request: RenderRequest) -> Optional[str]:
        image_urls = request.fabric.image_urls
        return image_urls.swatch or image_urls.macro or (image_urls.extra[0] if image_urls.extra else None)

    def _build_product_sheet_prompt(
        self,
        request: RenderRequest,
        notes_for_prompt: list[str],
    ) -> str:
        params = request.params
        outfit = params.outfit
        jacket = outfit.jacket
        trousers = outfit.trousers
        vest = outfit.vest
        shirt = outfit.shirt
        neckwear = outfit.neckwear

        style_keywords = ", ".join(params.style_keywords) if params.style_keywords else "minimal, refined"
        notes_text = "\n".join(f"- {note}" for note in notes_for_prompt) if notes_for_prompt else ""

        prompt = f"""Create a photorealistic product sheet of a male model wearing a bespoke tailored outfit.

STYLE GOAL:
- Clean product sheet layout, minimal typography, no visible text overlays
- Neutral background, studio lighting, sharp garment details
- The model wears the garment; realistic photography only

OUTFIT DETAILS:
- Jacket type: {jacket.type}
- Lapel: {jacket.lapel}
- Buttons: {jacket.buttons}
- Fit: {jacket.fit or 'tailored'}
- Trousers: {trousers.type} (rise: {trousers.rise or 'mid'})
- Vest/waistcoat: {'included' if vest.enabled else 'not included'}
- Shirt: {shirt.collar or 'spread'} collar, color {shirt.color or 'white'}
- Neckwear: {neckwear.type} ({neckwear.color or 'classic'})
- Occasion: {params.occasion or 'formal'}

FABRIC GUIDANCE:
- Color hint: {request.fabric.color or 'classic tone'}
- Pattern hint: {request.fabric.pattern or 'solid'}
- Composition: {request.fabric.composition or 'fine wool'}

IMPORTANT:
- Do NOT attempt to replicate any specific fabric pattern; the real fabric reference will be overlaid separately.
- Leave the bottom 10% of the image visually calm and uncluttered for a fabric overlay.
- Avoid busy props; focus on the garment.

STYLE KEYWORDS: {style_keywords}
{notes_text}
"""

        return prompt

    def _download_image(self, url: str) -> Image.Image:
        """
        Download image from URL or load from local filesystem.

        Args:
            url: Image URL (absolute HTTP/HTTPS URL or relative local path)

        Returns:
            PIL Image
        """
        if Image is None:
            raise RuntimeError("Pillow not installed; cannot download images")

        # Handle relative fabric paths (e.g., /fabrics/images/60T1003.jpg)
        if url.startswith("/fabrics/"):
            # Convert to local filesystem path
            project_root = Path(__file__).parent.parent
            local_path = project_root / "storage" / url.lstrip("/")

            if local_path.exists():
                logger.info(f"[DALLETool] Loading fabric image from local path: {local_path}")
                return Image.open(local_path)
            else:
                logger.warning(f"[DALLETool] Local fabric image not found: {local_path}")
                raise FileNotFoundError(f"Fabric image not found: {local_path}")

        # Handle absolute URLs (http://, https://)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))

    def _create_composite_with_fabric_thumbnails(
        self,
        mood_board: Image.Image,
        fabrics: List[Dict[str, Any]],
    ) -> Image.Image:
        """
        Create composite image: mood board + fabric thumbnails.

        Args:
            mood_board: DALL-E generated mood board
            fabrics: Fabric data with image URLs (max 2)

        Returns:
            Composite PIL Image
        """
        if Image is None:
            raise RuntimeError("Pillow not installed; cannot compose images")

        # Mood board dimensions
        mb_width, mb_height = mood_board.size

        # Thumbnail size (10% of mood board height)
        thumb_height = int(mb_height * 0.10)
        thumb_width = thumb_height  # Square thumbnails

        # Download and resize fabric images
        fabric_thumbnails = []
        for fabric in fabrics[:2]:
            image_urls = fabric.get("image_urls", [])
            if not image_urls or not image_urls[0]:
                continue

            try:
                fabric_img = self._download_image(image_urls[0])
                # Resize to thumbnail
                fabric_img.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                fabric_thumbnails.append({
                    "image": fabric_img,
                    "fabric_code": fabric.get("fabric_code", ""),
                    "name": fabric.get("name", ""),
                })
            except Exception as e:
                logger.warning(f"[DALLETool] Failed to download fabric image: {e}")
                continue

        if not fabric_thumbnails:
            logger.info("[DALLETool] No fabric thumbnails available, returning original mood board")
            return mood_board

        # Create composite (paste thumbnails on mood board)
        composite = mood_board.copy()
        draw = ImageDraw.Draw(composite)

        # Position thumbnails at bottom-right corner
        padding = 20
        x_offset = mb_width - thumb_width - padding
        y_offset = mb_height - (thumb_height * len(fabric_thumbnails)) - (padding * len(fabric_thumbnails))

        for i, thumb_data in enumerate(fabric_thumbnails):
            thumb_img = thumb_data["image"]
            fabric_code = thumb_data["fabric_code"]

            # Calculate position
            x = x_offset
            y = y_offset + (i * (thumb_height + padding))

            # Draw white background box
            box_padding = 5
            draw.rectangle(
                [
                    x - box_padding,
                    y - box_padding,
                    x + thumb_width + box_padding,
                    y + thumb_height + box_padding + 20,  # Extra space for text
                ],
                fill="white",
                outline="black",
                width=2,
            )

            # Paste thumbnail
            composite.paste(thumb_img, (x, y))

            # Add fabric code text
            try:
                # Try to load a font, fallback to default
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            except:
                font = ImageFont.load_default()

            text_y = y + thumb_height + 2
            draw.text((x, text_y), f"Ref: {fabric_code}", fill="black", font=font)

        logger.info(f"[DALLETool] Added {len(fabric_thumbnails)} fabric thumbnails to mood board")
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


# Singleton instance
_dalle_tool: Optional[DALLETool] = None


def get_dalle_tool() -> DALLETool:
    """
    Get or create singleton DALLE tool instance.

    Returns:
        DALLETool instance
    """
    global _dalle_tool
    if _dalle_tool is None:
        _dalle_tool = DALLETool()
        logger.info("[DALLETool] Singleton instance created")
    return _dalle_tool
