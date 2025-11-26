"""
HENK Fabric Processor
Processes scraped fabric data and integrates with RAG system using OpenAI embeddings.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import tiktoken
from openai import AsyncOpenAI

from config.fabric_config import (
    config, FABRIC_CATEGORIES, FABRIC_COMPOSITIONS,
    FABRIC_PATTERNS, FABRIC_WEIGHTS, FABRIC_FINISHES
)
from temp_review.modules.fabric_scraper import FabricData

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


@dataclass
class FabricChunk:
    """Represents a chunk of fabric data for RAG"""
    fabric_code: str
    chunk_id: str
    content: str
    chunk_type: str  # 'characteristics', 'visual', 'usage', 'technical'
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class FabricProcessor:
    """
    Processes fabric data for RAG integration.
    Generates embeddings and manages vector storage.
    """

    def __init__(self):
        self.config = config
        self.openai_client: Optional[AsyncOpenAI] = None
        self.tokenizer = None

        if config.is_openai_configured():
            self.openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            self.tokenizer = tiktoken.encoding_for_model(config.OPENAI_EMBEDDING_MODEL)
        else:
            logger.warning("OpenAI not configured. Embedding functionality disabled.")

    async def process_fabric(self, fabric: FabricData) -> List[FabricChunk]:
        """
        Process a single fabric into chunks with embeddings.

        Args:
            fabric: FabricData object

        Returns:
            List of FabricChunk objects with embeddings
        """
        try:
            logger.info(f"Processing fabric {fabric['fabric_code']}")

            # Create chunks
            chunks = self._create_fabric_chunks(fabric)

            # Generate embeddings
            if self.openai_client and chunks:
                chunks = await self._generate_embeddings(chunks)

            return chunks

        except Exception as e:
            logger.error(f"Error processing fabric {fabric.get('fabric_code', 'unknown')}: {str(e)}")
            return []

    def _create_fabric_chunks(self, fabric: FabricData) -> List[FabricChunk]:
        """
        Create optimized chunks from fabric data.
        Different chunk types for different aspects of the fabric.
        """
        chunks = []

        # 1. Characteristics chunk (composition, weight, texture)
        characteristics = self._build_characteristics_chunk(fabric)
        if characteristics:
            chunks.append(FabricChunk(
                fabric_code=fabric.fabric_code,
                chunk_id=f"{fabric.fabric_code}_characteristics",
                content=characteristics,
                chunk_type='characteristics',
                metadata=self._extract_metadata(fabric, 'characteristics')
            ))

        # 2. Visual descriptors chunk (color, pattern, finish)
        visual = self._build_visual_chunk(fabric)
        if visual:
            chunks.append(FabricChunk(
                fabric_code=fabric.fabric_code,
                chunk_id=f"{fabric.fabric_code}_visual",
                content=visual,
                chunk_type='visual',
                metadata=self._extract_metadata(fabric, 'visual')
            ))

        # 3. Usage recommendations chunk (season, occasion, style)
        usage = self._build_usage_chunk(fabric)
        if usage:
            chunks.append(FabricChunk(
                fabric_code=fabric.fabric_code,
                chunk_id=f"{fabric.fabric_code}_usage",
                content=usage,
                chunk_type='usage',
                metadata=self._extract_metadata(fabric, 'usage')
            ))

        # 4. Technical specifications chunk (care, durability)
        technical = self._build_technical_chunk(fabric)
        if technical:
            chunks.append(FabricChunk(
                fabric_code=fabric.fabric_code,
                chunk_id=f"{fabric.fabric_code}_technical",
                content=technical,
                chunk_type='technical',
                metadata=self._extract_metadata(fabric, 'technical')
            ))

        return chunks

    def _build_characteristics_chunk(self, fabric: FabricData) -> str:
        """Build characteristics description"""
        parts = [f"Fabric Code: {fabric.fabric_code}"]

        if fabric.name:
            parts.append(f"Name: {fabric.name}")

        if fabric.composition:
            parts.append(f"Composition: {fabric.composition}")
        else:
            # Try to infer composition from name or description
            inferred_comp = self._infer_composition(fabric)
            if inferred_comp:
                parts.append(f"Composition: {inferred_comp}")

        if fabric.weight:
            parts.append(f"Weight: {fabric.weight}g/m²")
            weight_category = self._categorize_weight(fabric.weight)
            parts.append(f"Weight Category: {weight_category}")

        if fabric.description:
            parts.append(f"Description: {fabric.description}")

        return " | ".join(parts)

    def _build_visual_chunk(self, fabric: FabricData) -> str:
        """Build visual description"""
        parts = [f"Fabric Code: {fabric.fabric_code}"]

        if fabric.color:
            parts.append(f"Color: {fabric.color}")

        if fabric.pattern:
            parts.append(f"Pattern: {fabric.pattern}")
        else:
            # Try to infer pattern
            inferred_pattern = self._infer_pattern(fabric)
            if inferred_pattern:
                parts.append(f"Pattern: {inferred_pattern}")

        # Infer finish/texture
        finish = self._infer_finish(fabric)
        if finish:
            parts.append(f"Finish: {finish}")

        if fabric.image_urls:
            parts.append(f"Has {len(fabric.image_urls)} reference image(s)")

        return " | ".join(parts)

    def _build_usage_chunk(self, fabric: FabricData) -> str:
        """Build usage recommendations"""
        parts = [f"Fabric Code: {fabric.fabric_code}"]

        if fabric.season:
            parts.append(f"Seasons: {', '.join(fabric.season)}")
        elif fabric.weight:
            # Infer seasons from weight
            seasons = self._infer_seasons_from_weight(fabric.weight)
            if seasons:
                parts.append(f"Recommended Seasons: {', '.join(seasons)}")

        if fabric.category:
            parts.append(f"Category: {fabric.category}")
            if fabric.category in FABRIC_CATEGORIES:
                occasions = FABRIC_CATEGORIES[fabric.category].get('occasions', [])
                parts.append(f"Suitable Occasions: {', '.join(occasions)}")

        # Build style recommendations
        style_recs = self._generate_style_recommendations(fabric)
        if style_recs:
            parts.append(f"Style Recommendations: {style_recs}")

        return " | ".join(parts)

    def _build_technical_chunk(self, fabric: FabricData) -> str:
        """Build technical specifications"""
        parts = [f"Fabric Code: {fabric.fabric_code}"]

        if fabric.care_instructions:
            parts.append(f"Care: {fabric.care_instructions}")
        else:
            # Generate standard care instructions based on composition
            care = self._generate_care_instructions(fabric)
            if care:
                parts.append(f"Care Instructions: {care}")

        if fabric.supplier:
            parts.append(f"Supplier: {fabric.supplier}")

        if fabric.origin:
            parts.append(f"Origin: {fabric.origin}")

        if fabric.stock_status:
            parts.append(f"Stock Status: {fabric.stock_status}")

        # Add durability assessment
        durability = self._assess_durability(fabric)
        if durability:
            parts.append(f"Durability: {durability}")

        return " | ".join(parts)

    def _extract_metadata(self, fabric: FabricData, chunk_type: str) -> Dict[str, Any]:
        """Extract relevant metadata for a chunk"""
        base_metadata = {
            'fabric_code': fabric.fabric_code,
            'chunk_type': chunk_type,
            'supplier': fabric.supplier or 'Formens',
            'scrape_date': fabric.scrape_date
        }

        if chunk_type == 'characteristics':
            base_metadata.update({
                'composition': fabric.composition,
                'weight': fabric.weight,
                'weight_category': self._categorize_weight(fabric.weight) if fabric.weight else None
            })
        elif chunk_type == 'visual':
            base_metadata.update({
                'color': fabric.color,
                'pattern': fabric.pattern or self._infer_pattern(fabric),
                'has_images': bool(fabric.image_urls)
            })
        elif chunk_type == 'usage':
            base_metadata.update({
                'seasons': fabric.season or (self._infer_seasons_from_weight(fabric.weight) if fabric.weight else []),
                'category': fabric.category,
                'occasions': FABRIC_CATEGORIES.get(fabric.category, {}).get('occasions', []) if fabric.category else []
            })
        elif chunk_type == 'technical':
            base_metadata.update({
                'stock_status': fabric.stock_status,
                'origin': fabric.origin,
            })

        return base_metadata

    async def _generate_embeddings(self, chunks: List[FabricChunk]) -> List[FabricChunk]:
        """Generate embeddings for chunks using OpenAI"""
        if not self.openai_client:
            logger.warning("Cannot generate embeddings - OpenAI not configured")
            return chunks

        try:
            # Batch embedding generation
            texts = [chunk.content for chunk in chunks]

            logger.info(f"Generating embeddings for {len(texts)} chunks...")

            response = await self.openai_client.embeddings.create(
                model=config.OPENAI_EMBEDDING_MODEL,
                input=texts,
                dimensions=config.OPENAI_EMBEDDING_DIMENSIONS
            )

            for i, chunk in enumerate(chunks):
                chunk.embedding = response.data[i].embedding

            logger.info(f"Generated {len(chunks)} embeddings successfully")

            return chunks

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return chunks

    def _infer_composition(self, fabric: FabricData) -> Optional[str]:
        """Infer fabric composition from name or description"""
        text = f"{fabric.name or ''} {fabric.description or ''}".lower()

        for composition in FABRIC_COMPOSITIONS:
            if composition.replace('_', ' ') in text or composition.replace('_', '') in text:
                return composition.replace('_', ' ').title()

        return None

    def _infer_pattern(self, fabric: FabricData) -> Optional[str]:
        """Infer fabric pattern from name or description"""
        text = f"{fabric.name or ''} {fabric.description or ''}".lower()

        for pattern in FABRIC_PATTERNS:
            if pattern.replace('_', ' ') in text or pattern.replace('_', '') in text:
                return pattern.replace('_', ' ').title()

        return "Solid"  # Default

    def _infer_finish(self, fabric: FabricData) -> Optional[str]:
        """Infer fabric finish from name or description"""
        text = f"{fabric.name or ''} {fabric.description or ''}".lower()

        for finish in FABRIC_FINISHES:
            if finish.replace('_', ' ') in text:
                return finish.replace('_', ' ').title()

        return "Smooth"  # Default

    def _categorize_weight(self, weight: int) -> str:
        """Categorize fabric weight"""
        for category, props in FABRIC_WEIGHTS.items():
            if props['min'] <= weight < props['max']:
                return category.title()
        return "Unknown"

    def _infer_seasons_from_weight(self, weight: int) -> List[str]:
        """Infer suitable seasons from fabric weight"""
        for category, props in FABRIC_WEIGHTS.items():
            if props['min'] <= weight < props['max']:
                return props['seasons']
        return []

    def _generate_style_recommendations(self, fabric: FabricData) -> str:
        """Generate style recommendations based on fabric properties"""
        recommendations = []

        # Based on weight
        if fabric.weight:
            if fabric.weight < 250:
                recommendations.append("ideal for unlined or half-lined jackets")
            elif fabric.weight < 350:
                recommendations.append("versatile for year-round suits")
            else:
                recommendations.append("excellent for structured winter suits")

        # Based on pattern
        pattern = fabric.pattern or self._infer_pattern(fabric)
        if pattern and pattern.lower() in ['striped', 'pinstripe']:
            recommendations.append("professional business look")
        elif pattern and pattern.lower() in ['checked', 'plaid']:
            recommendations.append("smart casual or country style")
        elif pattern and pattern.lower() == 'solid':
            recommendations.append("timeless classic elegance")

        return ", ".join(recommendations) if recommendations else ""

    def _generate_care_instructions(self, fabric: FabricData) -> str:
        """Generate care instructions based on composition"""
        composition = fabric.composition or self._infer_composition(fabric)

        if not composition:
            return "Professional dry cleaning recommended"

        composition_lower = composition.lower()

        if 'wool' in composition_lower:
            return "Dry clean only, steam to remove wrinkles, store with moth protection"
        elif 'linen' in composition_lower:
            return "Dry clean or gentle hand wash, iron while damp, store in breathable garment bag"
        elif 'cotton' in composition_lower:
            return "Dry clean or machine wash cold, tumble dry low, iron as needed"
        elif 'silk' in composition_lower:
            return "Dry clean only, avoid direct sunlight, store in cool dry place"
        else:
            return "Dry clean recommended, follow care label instructions"

    def _assess_durability(self, fabric: FabricData) -> str:
        """Assess fabric durability"""
        composition = fabric.composition or self._infer_composition(fabric)

        if not composition:
            return "Good"

        composition_lower = composition.lower()

        if 'wool' in composition_lower and 'blend' not in composition_lower:
            return "Excellent - natural resilience and longevity"
        elif 'polyester' in composition_lower or 'synthetic' in composition_lower:
            return "Very Good - wrinkle-resistant and durable"
        elif 'linen' in composition_lower:
            return "Good - durable but prone to wrinkling"
        elif 'cotton' in composition_lower:
            return "Good - comfortable but may wrinkle"
        else:
            return "Good"

    async def process_batch(self, fabrics: List[FabricData]) -> List[FabricChunk]:
        """Process multiple fabrics in batch"""
        all_chunks = []

        for fabric in fabrics:
            chunks = await self.process_fabric(fabric)
            all_chunks.extend(chunks)

        logger.info(f"Processed {len(fabrics)} fabrics into {len(all_chunks)} chunks")

        return all_chunks

    def save_processed_data(self, chunks: List[FabricChunk], output_path: Optional[Path] = None):
        """Save processed chunks to JSON"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = Path(config.FABRIC_DATA_STORAGE) / f"processed_{timestamp}.json"

            data = {
                'processed_date': datetime.utcnow().isoformat(),
                'total_chunks': len(chunks),
                'chunks': [
                    {
                        'fabric_code': chunk.fabric_code,
                        'chunk_id': chunk.chunk_id,
                        'content': chunk.content,
                        'chunk_type': chunk.chunk_type,
                        'metadata': chunk.metadata,
                        'embedding': chunk.embedding
                    }
                    for chunk in chunks
                ]
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(chunks)} processed chunks to {output_path}")

        except Exception as e:
            logger.error(f"Error saving processed data: {str(e)}")

    def load_processed_data(self, input_path: Path) -> List[FabricChunk]:
        """Load processed chunks from JSON"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            chunks = []
            for chunk_data in data.get('chunks', []):
                chunk = FabricChunk(
                    fabric_code=chunk_data['fabric_code'],
                    chunk_id=chunk_data['chunk_id'],
                    content=chunk_data['content'],
                    chunk_type=chunk_data['chunk_type'],
                    metadata=chunk_data['metadata'],
                    embedding=chunk_data.get('embedding')
                )
                chunks.append(chunk)

            logger.info(f"Loaded {len(chunks)} chunks from {input_path}")
            return chunks

        except Exception as e:
            logger.error(f"Error loading processed data: {str(e)}")
            return []

    async def similarity_search(
        self,
        query: str,
        chunks: List[FabricChunk],
        top_k: int = None
    ) -> List[Tuple[FabricChunk, float]]:
        """
        Perform similarity search on fabric chunks.

        Args:
            query: Search query
            chunks: List of FabricChunk objects with embeddings
            top_k: Number of results to return

        Returns:
            List of (chunk, similarity_score) tuples
        """
        if not self.openai_client:
            logger.error("Cannot perform similarity search - OpenAI not configured")
            return []

        top_k = top_k or config.RAG_TOP_K_RESULTS

        try:
            # Generate query embedding
            response = await self.openai_client.embeddings.create(
                model=config.OPENAI_EMBEDDING_MODEL,
                input=query,
                dimensions=config.OPENAI_EMBEDDING_DIMENSIONS
            )

            query_embedding = np.array(response.data[0].embedding)

            # Calculate cosine similarity with all chunks
            results = []
            for chunk in chunks:
                if chunk.embedding:
                    chunk_embedding = np.array(chunk.embedding)
                    similarity = np.dot(query_embedding, chunk_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                    )
                    if similarity >= config.RAG_SIMILARITY_THRESHOLD:
                        results.append((chunk, float(similarity)))

            # Sort by similarity
            results.sort(key=lambda x: x[1], reverse=True)

            return results[:top_k]

        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return []


async def main():
    """Example usage"""
    # Load scraped data
    data_path = Path(config.FABRIC_DATA_STORAGE) / "fabrics_latest.json"

    if not data_path.exists():
        logger.error("No scraped fabric data found. Run fabric_scraper.py first.")
        return

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fabrics = [FabricData(**fabric_dict) for fabric_dict in data.get('fabrics', [])]

    logger.info(f"Loaded {len(fabrics)} fabrics")

    # Process fabrics
    processor = FabricProcessor()
    chunks = await processor.process_batch(fabrics[:5])  # Process first 5 for testing

    # Save processed data
    processor.save_processed_data(chunks)

    # Test similarity search
    if chunks and chunks[0].embedding:
        results = await processor.similarity_search(
            "lightweight summer fabric for ceremony",
            chunks
        )

        logger.info(f"\nSimilarity search results:")
        for chunk, score in results[:3]:
            logger.info(f"Score: {score:.3f} | {chunk.content}")


if __name__ == "__main__":
    asyncio.run(main())
