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

    async def generate_image(self, request: DALLEImageRequest) -> DALLEImageResponse:
        """
        Generate image with DALL-E 3.

        Args:
            request: Image generation parameters

        Returns:
            Generated image response
        """
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
            )
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
        if design_preferences:
            revers = design_preferences.get("revers_type", "")
            shoulder = design_preferences.get("shoulder_padding", "")
            waistband = design_preferences.get("waistband_type", "")

            if revers or shoulder or waistband:
                design_details = "\n\nSUIT DESIGN:"
                if revers:
                    design_details += f"\n- Lapel style: {revers}"
                if shoulder:
                    design_details += f"\n- Shoulder: {shoulder}"
                if waistband:
                    design_details += f"\n- Trouser waistband: {waistband}"

        # Build final prompt
        prompt = f"""Create an elegant mood board for a bespoke men's suit in a {scene}.

FABRIC REFERENCE: Show suits made from {fabrics_text}.{design_details}

STYLE: {style}, sophisticated, high-quality menswear photography.

COMPOSITION: Professional fashion editorial style, clean layout, luxurious atmosphere.

SETTING: {occasion} - create the appropriate ambiance and backdrop.

NOTE: Leave bottom-right corner clear (for fabric swatches overlay)."""

        logger.info(f"[DALLETool] Generated prompt: {prompt[:200]}...")
        return prompt

    def _download_image(self, url: str) -> Image.Image:
        """
        Download image from URL.

        Args:
            url: Image URL

        Returns:
            PIL Image
        """
        if Image is None:
            raise RuntimeError("Pillow not installed; cannot download images")

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
