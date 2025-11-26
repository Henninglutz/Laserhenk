"""
HENK Outfit Generator
Generates outfit visualizations using DALL-E based on fabric data.
Integrates with HENK's H3 design phase workflow.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import io

from openai import AsyncOpenAI
from PIL import Image
import aiohttp

from config.fabric_config import config, FABRIC_CATEGORIES
from temp_review.modules.fabric_scraper import FabricData
from temp_review.modules.fabric_processor import FabricProcessor

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


@dataclass
class OutfitSpec:
    """Specification for outfit generation"""
    occasion: str  # wedding, business, casual, etc.
    season: str  # spring, summer, fall, winter
    style_preferences: List[str]  # classic, modern, bold, etc.
    color_preferences: Optional[List[str]] = None
    pattern_preferences: Optional[List[str]] = None
    fabrics: Optional[List[FabricData]] = None
    additional_notes: Optional[str] = None


@dataclass
class GeneratedOutfit:
    """Result of outfit generation"""
    outfit_id: str
    spec: OutfitSpec
    fabrics_used: List[str]  # Fabric codes
    dalle_prompt: str
    image_url: Optional[str] = None
    local_image_path: Optional[str] = None
    revised_prompt: Optional[str] = None  # DALL-E's revised prompt
    generation_date: str = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.generation_date is None:
            self.generation_date = datetime.utcnow().isoformat()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert OutfitSpec to dict
        data['spec'] = asdict(self.spec)
        return data


class OutfitGenerator:
    """
    Generates outfit visualizations using DALL-E.
    Maps fabric data to visual outfit representations.
    """

    def __init__(self):
        self.config = config
        self.openai_client: Optional[AsyncOpenAI] = None
        self.fabric_processor = FabricProcessor()

        if config.is_openai_configured():
            self.openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI not configured. Outfit generation disabled.")

        # Ensure output directory exists
        self.output_dir = Path(config.FABRIC_STORAGE_PATH) / "generated_outfits"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_outfit(
        self,
        spec: OutfitSpec,
        use_rag: bool = True
    ) -> Optional[GeneratedOutfit]:
        """
        Generate outfit visualization based on specification.

        Args:
            spec: OutfitSpec with requirements
            use_rag: Whether to use RAG to find suitable fabrics

        Returns:
            GeneratedOutfit object with image
        """
        if not self.openai_client:
            logger.error("Cannot generate outfit - OpenAI not configured")
            return None

        try:
            logger.info(f"Generating outfit for {spec.occasion} in {spec.season}")

            # Find suitable fabrics if not provided
            if not spec.fabrics and use_rag:
                spec.fabrics = await self._find_suitable_fabrics(spec)

            if not spec.fabrics:
                logger.warning("No suitable fabrics found for specification")
                # Continue anyway with general prompt

            # Build DALL-E prompt
            dalle_prompt = self._build_dalle_prompt(spec)

            logger.info(f"DALL-E Prompt: {dalle_prompt}")

            # Generate image
            response = await self.openai_client.images.generate(
                model=config.OPENAI_DALLE_MODEL,
                prompt=dalle_prompt,
                size=config.OPENAI_DALLE_SIZE,
                quality=config.OPENAI_DALLE_QUALITY,
                n=1
            )

            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt if hasattr(response.data[0], 'revised_prompt') else None

            # Download and save image
            outfit_id = self._generate_outfit_id(spec)
            local_path = await self._download_outfit_image(image_url, outfit_id)

            # Create result
            outfit = GeneratedOutfit(
                outfit_id=outfit_id,
                spec=spec,
                fabrics_used=[f.fabric_code for f in spec.fabrics] if spec.fabrics else [],
                dalle_prompt=dalle_prompt,
                image_url=image_url,
                local_image_path=str(local_path) if local_path else None,
                revised_prompt=revised_prompt,
                metadata={
                    'model': config.OPENAI_DALLE_MODEL,
                    'size': config.OPENAI_DALLE_SIZE,
                    'quality': config.OPENAI_DALLE_QUALITY
                }
            )

            # Save metadata
            self._save_outfit_metadata(outfit)

            logger.info(f"Generated outfit {outfit_id}")

            return outfit

        except Exception as e:
            logger.error(f"Error generating outfit: {str(e)}")
            return None

    async def generate_outfit_variants(
        self,
        spec: OutfitSpec,
        num_variants: int = 3
    ) -> List[GeneratedOutfit]:
        """
        Generate multiple outfit variants based on specification.

        Args:
            spec: OutfitSpec with requirements
            num_variants: Number of variants to generate

        Returns:
            List of GeneratedOutfit objects
        """
        variants = []

        for i in range(num_variants):
            logger.info(f"Generating variant {i+1}/{num_variants}")

            # Modify spec slightly for variation
            variant_spec = self._create_variant_spec(spec, i)

            outfit = await self.generate_outfit(variant_spec, use_rag=True)
            if outfit:
                variants.append(outfit)

            # Small delay between generations
            await asyncio.sleep(2)

        logger.info(f"Generated {len(variants)} outfit variants")
        return variants

    def _build_dalle_prompt(self, spec: OutfitSpec) -> str:
        """
        Build detailed DALL-E prompt from outfit specification.
        """
        prompt_parts = []

        # Base description
        prompt_parts.append("Professional fashion photography of a complete men's tailored outfit,")

        # Occasion and style
        occasion_desc = self._get_occasion_description(spec.occasion)
        prompt_parts.append(occasion_desc)

        # Fabric details
        if spec.fabrics:
            fabric_descriptions = []
            for fabric in spec.fabrics[:2]:  # Use top 2 fabrics
                desc = self._fabric_to_description(fabric)
                if desc:
                    fabric_descriptions.append(desc)

            if fabric_descriptions:
                prompt_parts.append(f"made from {', '.join(fabric_descriptions)}")

        # Colors
        if spec.color_preferences:
            colors = ', '.join(spec.color_preferences[:3])
            prompt_parts.append(f"in {colors} tones")

        # Patterns
        if spec.pattern_preferences:
            patterns = ', '.join(spec.pattern_preferences[:2])
            prompt_parts.append(f"with {patterns} pattern")

        # Season
        season_desc = self._get_season_description(spec.season)
        if season_desc:
            prompt_parts.append(season_desc)

        # Style preferences
        if spec.style_preferences:
            style_desc = ', '.join(spec.style_preferences[:3])
            prompt_parts.append(f"{style_desc} style")

        # Additional notes
        if spec.additional_notes:
            prompt_parts.append(spec.additional_notes)

        # Photography style
        prompt_parts.append("displayed on a mannequin or laid flat, studio lighting, high-end fashion photography, detailed texture visible, professional styling, luxury menswear aesthetic")

        # Join all parts
        prompt = ' '.join(prompt_parts)

        # Ensure prompt is not too long (DALL-E has limits)
        if len(prompt) > 1000:
            prompt = prompt[:997] + "..."

        return prompt

    def _fabric_to_description(self, fabric: FabricData) -> str:
        """Convert fabric data to descriptive text for prompt"""
        parts = []

        if fabric.composition:
            parts.append(fabric.composition.lower())

        if fabric.weight:
            if fabric.weight < 250:
                parts.append("lightweight")
            elif fabric.weight < 350:
                parts.append("medium-weight")
            else:
                parts.append("heavyweight")

        if fabric.pattern:
            parts.append(fabric.pattern.lower())

        if fabric.color:
            parts.append(fabric.color.lower())

        if not parts:
            return f"premium {fabric.fabric_code} fabric"

        return ' '.join(parts)

    def _get_occasion_description(self, occasion: str) -> str:
        """Get description for occasion"""
        occasion_map = {
            'wedding': 'elegant wedding attire, formal ceremony suit',
            'business': 'professional business suit, corporate attire',
            'formal_event': 'black-tie formal evening wear',
            'gala': 'sophisticated gala evening suit',
            'casual': 'smart casual tailored outfit',
            'smart_casual': 'refined smart casual ensemble',
            'office': 'modern office suit, business professional',
            'weekend': 'relaxed weekend tailored look'
        }

        return occasion_map.get(occasion.lower(), f'{occasion} outfit')

    def _get_season_description(self, season: str) -> str:
        """Get seasonal styling description"""
        season_map = {
            'spring': 'spring/summer season, lighter construction',
            'summer': 'summer season, breathable fabric, unlined or half-lined',
            'fall': 'fall/autumn season, transitional weight',
            'winter': 'winter season, warm and structured'
        }

        return season_map.get(season.lower(), '')

    async def _find_suitable_fabrics(self, spec: OutfitSpec) -> List[FabricData]:
        """
        Use RAG to find suitable fabrics for outfit specification.
        """
        try:
            # Build search query
            query_parts = [
                f"{spec.occasion} occasion",
                f"{spec.season} season"
            ]

            if spec.color_preferences:
                query_parts.append(f"{', '.join(spec.color_preferences)} color")

            if spec.pattern_preferences:
                query_parts.append(f"{', '.join(spec.pattern_preferences)} pattern")

            if spec.style_preferences:
                query_parts.append(f"{', '.join(spec.style_preferences)} style")

            query = ' '.join(query_parts)

            logger.info(f"RAG query: {query}")

            # Load processed fabric chunks
            processed_path = Path(config.FABRIC_DATA_STORAGE) / "processed_latest.json"
            if not processed_path.exists():
                logger.warning("No processed fabric data found")
                return []

            chunks = self.fabric_processor.load_processed_data(processed_path)

            if not chunks or not chunks[0].embedding:
                logger.warning("No embeddings available for similarity search")
                return []

            # Perform similarity search
            results = await self.fabric_processor.similarity_search(
                query=query,
                chunks=chunks,
                top_k=5
            )

            if not results:
                logger.warning("No similar fabrics found")
                return []

            # Get unique fabric codes
            fabric_codes = list(set([chunk.fabric_code for chunk, _ in results]))

            # Load full fabric data
            fabrics_path = Path(config.FABRIC_DATA_STORAGE) / "fabrics_latest.json"
            if not fabrics_path.exists():
                return []

            with open(fabrics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Filter fabrics by codes
            fabrics = [
                FabricData(**fabric_dict)
                for fabric_dict in data.get('fabrics', [])
                if fabric_dict.get('fabric_code') in fabric_codes
            ]

            logger.info(f"Found {len(fabrics)} suitable fabrics via RAG")

            return fabrics[:3]  # Return top 3

        except Exception as e:
            logger.error(f"Error finding suitable fabrics: {str(e)}")
            return []

    def _create_variant_spec(self, base_spec: OutfitSpec, variant_index: int) -> OutfitSpec:
        """Create a variant of the outfit specification"""
        # Create copy of spec
        variant = OutfitSpec(
            occasion=base_spec.occasion,
            season=base_spec.season,
            style_preferences=base_spec.style_preferences.copy() if base_spec.style_preferences else [],
            color_preferences=base_spec.color_preferences.copy() if base_spec.color_preferences else None,
            pattern_preferences=base_spec.pattern_preferences.copy() if base_spec.pattern_preferences else None,
            fabrics=None,  # Will be found via RAG
            additional_notes=base_spec.additional_notes
        )

        # Modify slightly based on variant index
        style_variants = [
            ['classic', 'timeless'],
            ['modern', 'contemporary'],
            ['bold', 'distinctive']
        ]

        if variant_index < len(style_variants):
            variant.style_preferences = style_variants[variant_index]

        return variant

    async def _download_outfit_image(self, url: str, outfit_id: str) -> Optional[Path]:
        """Download generated outfit image"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    image_data = await response.read()
                    image = Image.open(io.BytesIO(image_data))

                    # Save image
                    filename = f"{outfit_id}.png"
                    output_path = self.output_dir / filename

                    image.save(output_path, "PNG")

                    logger.info(f"Saved outfit image to {output_path}")
                    return output_path

        except Exception as e:
            logger.error(f"Error downloading outfit image: {str(e)}")
            return None

    def _save_outfit_metadata(self, outfit: GeneratedOutfit):
        """Save outfit metadata to JSON"""
        try:
            metadata_path = self.output_dir / f"{outfit.outfit_id}.json"

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(outfit.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Saved outfit metadata to {metadata_path}")

        except Exception as e:
            logger.error(f"Error saving outfit metadata: {str(e)}")

    def _generate_outfit_id(self, spec: OutfitSpec) -> str:
        """Generate unique outfit ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        occasion_short = spec.occasion[:4].upper()
        season_short = spec.season[:2].upper()

        return f"OUTFIT_{occasion_short}_{season_short}_{timestamp}"

    async def generate_fabric_showcase(self, fabric: FabricData) -> Optional[GeneratedOutfit]:
        """
        Generate a showcase outfit featuring a specific fabric.

        Args:
            fabric: FabricData to showcase

        Returns:
            GeneratedOutfit object
        """
        # Create spec based on fabric properties
        spec = OutfitSpec(
            occasion=fabric.category or 'business',
            season=fabric.season[0] if fabric.season else 'spring',
            style_preferences=['elegant', 'refined'],
            color_preferences=[fabric.color] if fabric.color else None,
            pattern_preferences=[fabric.pattern] if fabric.pattern else None,
            fabrics=[fabric],
            additional_notes=f"Showcasing fabric {fabric.fabric_code}"
        )

        return await self.generate_outfit(spec, use_rag=False)

    def create_h3_outfit_prompt(
        self,
        client_preferences: Dict[str, Any],
        fabrics: List[FabricData]
    ) -> OutfitSpec:
        """
        Create outfit specification for HENK's H3 design phase.

        Args:
            client_preferences: Client style preferences and requirements
            fabrics: Available fabrics

        Returns:
            OutfitSpec ready for generation
        """
        spec = OutfitSpec(
            occasion=client_preferences.get('occasion', 'business'),
            season=client_preferences.get('season', 'spring'),
            style_preferences=client_preferences.get('style_preferences', ['classic']),
            color_preferences=client_preferences.get('color_preferences'),
            pattern_preferences=client_preferences.get('pattern_preferences'),
            fabrics=fabrics,
            additional_notes=client_preferences.get('notes')
        )

        return spec


async def main():
    """Example usage"""
    generator = OutfitGenerator()

    # Example 1: Generate outfit for wedding
    spec = OutfitSpec(
        occasion='wedding',
        season='summer',
        style_preferences=['classic', 'elegant'],
        color_preferences=['navy', 'light blue'],
        pattern_preferences=['solid'],
        additional_notes='For outdoor summer wedding ceremony'
    )

    outfit = await generator.generate_outfit(spec, use_rag=True)

    if outfit:
        logger.info(f"\nGenerated outfit {outfit.outfit_id}")
        logger.info(f"Prompt: {outfit.dalle_prompt}")
        logger.info(f"Image saved to: {outfit.local_image_path}")

    # Example 2: Generate variants
    logger.info("\n=== Generating variants ===")
    variants = await generator.generate_outfit_variants(spec, num_variants=2)

    logger.info(f"Generated {len(variants)} variants")


if __name__ == "__main__":
    asyncio.run(main())
