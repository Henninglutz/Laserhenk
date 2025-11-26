"""
HENK Fabric Module
Web scraping, RAG processing, and DALL-E integration for fabric data.
"""

__version__ = "1.0.0"

from .fabric_scraper import FabricData, FormensScraper
from .fabric_processor import FabricProcessor, FabricChunk
from .outfit_generator import OutfitGenerator, OutfitSpec, GeneratedOutfit

__all__ = [
    'FabricData',
    'FormensScraper',
    'FabricProcessor',
    'FabricChunk',
    'OutfitGenerator',
    'OutfitSpec',
    'GeneratedOutfit'
]
