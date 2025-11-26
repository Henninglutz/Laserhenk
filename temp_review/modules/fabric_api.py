"""
HENK Fabric API
REST API endpoints for fabric data, RAG search, and outfit generation.
"""

import asyncio
import logging
from functools import wraps

from flask import Blueprint, request, jsonify, send_file
from openai import AsyncOpenAI

from config.fabric_config import config
from database.db_manager import DatabaseManager
from database.models import Fabric
from temp_review.modules.fabric_processor import FabricProcessor
from temp_review.modules.outfit_generator import OutfitGenerator, OutfitSpec

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Create Blueprint
fabric_api = Blueprint('fabric_api', __name__, url_prefix='/api/fabrics')

# Initialize components
db_manager = DatabaseManager() if config.is_database_configured() else None
fabric_processor = FabricProcessor()
outfit_generator = OutfitGenerator()


def async_route(f):
    """Decorator to handle async routes in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


def require_database(f):
    """Decorator to require database configuration"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not db_manager:
            return jsonify({
                'error': 'Database not configured',
                'message': 'Please set DATABASE_URL in environment variables'
            }), 503
        return f(*args, **kwargs)
    return wrapper


def require_openai(f):
    """Decorator to require OpenAI configuration"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not config.is_openai_configured():
            return jsonify({
                'error': 'OpenAI not configured',
                'message': 'Please set OPENAI_API_KEY in environment variables'
            }), 503
        return f(*args, **kwargs)
    return wrapper


# ============================================================================
# Fabric Endpoints
# ============================================================================

@fabric_api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = {
        'status': 'healthy',
        'database_configured': config.is_database_configured(),
        'openai_configured': config.is_openai_configured(),
        'scraping_enabled': config.ENABLE_SCRAPING,
        'rag_enabled': config.ENABLE_RAG,
        'dalle_enabled': config.ENABLE_DALLE
    }

    if db_manager:
        try:
            stats = db_manager.get_stats()
            status['database_stats'] = stats
        except Exception as e:
            status['database_error'] = str(e)

    return jsonify(status), 200


@fabric_api.route('/', methods=['GET'])
@require_database
def get_fabrics():
    """
    Get all fabrics with optional filtering.

    Query params:
        - limit: Max number of results
        - category: Filter by category
        - season: Filter by season
        - color: Filter by color
        - pattern: Filter by pattern
    """
    try:
        limit = request.args.get('limit', type=int)
        category = request.args.get('category')
        season = request.args.get('season')

        if category:
            fabrics = db_manager.get_fabrics_by_category(category)
        elif season:
            fabrics = db_manager.get_fabrics_by_season(season)
        else:
            fabrics = db_manager.get_all_fabrics(limit=limit)

        return jsonify({
            'total': len(fabrics),
            'fabrics': [fabric.to_dict() for fabric in fabrics]
        }), 200

    except Exception as e:
        logger.error(f"Error getting fabrics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@fabric_api.route('/<fabric_code>', methods=['GET'])
@require_database
def get_fabric(fabric_code: str):
    """Get specific fabric by code"""
    try:
        fabric = db_manager.get_fabric_by_code(fabric_code)

        if not fabric:
            return jsonify({'error': 'Fabric not found'}), 404

        return jsonify(fabric.to_dict()), 200

    except Exception as e:
        logger.error(f"Error getting fabric: {str(e)}")
        return jsonify({'error': str(e)}), 500


@fabric_api.route('/search', methods=['POST'])
@require_database
@require_openai
@async_route
async def search_fabrics():
    """
    Search fabrics using RAG (semantic search).

    Body:
        {
            "query": "lightweight summer fabric for wedding",
            "limit": 5,
            "threshold": 0.7
        }
    """
    try:
        data = request.get_json()

        if not data or 'query' not in data:
            return jsonify({'error': 'Query required'}), 400

        query = data['query']
        limit = data.get('limit', config.RAG_TOP_K_RESULTS)
        threshold = data.get('threshold', config.RAG_SIMILARITY_THRESHOLD)

        logger.info(f"Searching fabrics: {query}")

        # Generate query embedding
        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        response = await openai_client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=query,
            dimensions=config.OPENAI_EMBEDDING_DIMENSIONS
        )

        query_embedding = response.data[0].embedding

        # Search database
        results = db_manager.search_fabrics_by_vector(
            query_embedding=query_embedding,
            limit=limit,
            threshold=threshold
        )

        return jsonify({
            'query': query,
            'total': len(results),
            'results': [
                {
                    'fabric': fabric.to_dict(),
                    'similarity_score': round(score, 3)
                }
                for fabric, score in results
            ]
        }), 200

    except Exception as e:
        logger.error(f"Error searching fabrics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@fabric_api.route('/recommend', methods=['POST'])
@require_database
@require_openai
@async_route
async def recommend_fabrics():
    """
    Get fabric recommendations based on preferences.

    Body:
        {
            "occasion": "wedding",
            "season": "summer",
            "style_preferences": ["classic", "elegant"],
            "color_preferences": ["navy", "light blue"],
            "limit": 3
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        # Build query from preferences
        query_parts = []

        if data.get('occasion'):
            query_parts.append(f"{data['occasion']} occasion")

        if data.get('season'):
            query_parts.append(f"{data['season']} season")

        if data.get('style_preferences'):
            query_parts.append(f"{', '.join(data['style_preferences'])} style")

        if data.get('color_preferences'):
            query_parts.append(f"{', '.join(data['color_preferences'])} color")

        if data.get('pattern_preferences'):
            query_parts.append(f"{', '.join(data['pattern_preferences'])} pattern")

        query = ' '.join(query_parts)
        limit = data.get('limit', 3)

        logger.info(f"Recommending fabrics: {query}")

        # Generate query embedding
        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        response = await openai_client.embeddings.create(
            model=config.OPENAI_EMBEDDING_MODEL,
            input=query,
            dimensions=config.OPENAI_EMBEDDING_DIMENSIONS
        )

        query_embedding = response.data[0].embedding

        # Search database
        results = db_manager.search_fabrics_by_vector(
            query_embedding=query_embedding,
            limit=limit,
            threshold=0.6  # Lower threshold for recommendations
        )

        return jsonify({
            'preferences': data,
            'query': query,
            'total': len(results),
            'recommendations': [
                {
                    'fabric': fabric.to_dict(),
                    'match_score': round(score, 3),
                    'reason': f"Matches {data.get('occasion', 'your')} occasion in {data.get('season', 'any')} season"
                }
                for fabric, score in results
            ]
        }), 200

    except Exception as e:
        logger.error(f"Error recommending fabrics: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Outfit Generation Endpoints
# ============================================================================

@fabric_api.route('/outfits/generate', methods=['POST'])
@require_openai
@async_route
async def generate_outfit():
    """
    Generate outfit visualization using DALL-E.

    Body:
        {
            "occasion": "wedding",
            "season": "summer",
            "style_preferences": ["classic", "elegant"],
            "color_preferences": ["navy", "light blue"],
            "pattern_preferences": ["solid"],
            "fabric_codes": ["34C4054"],  // Optional
            "additional_notes": "For outdoor ceremony",
            "use_rag": true
        }
    """
    try:
        data = request.get_json()

        if not data or 'occasion' not in data or 'season' not in data:
            return jsonify({'error': 'occasion and season required'}), 400

        # Get fabrics if provided
        fabrics = None
        if data.get('fabric_codes'):
            if db_manager:
                fabrics = [
                    db_manager.get_fabric_by_code(code)
                    for code in data['fabric_codes']
                ]
                fabrics = [f for f in fabrics if f]  # Filter None values

        # Create outfit spec
        spec = OutfitSpec(
            occasion=data['occasion'],
            season=data['season'],
            style_preferences=data.get('style_preferences', ['classic']),
            color_preferences=data.get('color_preferences'),
            pattern_preferences=data.get('pattern_preferences'),
            fabrics=fabrics,
            additional_notes=data.get('additional_notes')
        )

        # Generate outfit
        use_rag = data.get('use_rag', True) and db_manager is not None
        outfit = await outfit_generator.generate_outfit(spec, use_rag=use_rag)

        if not outfit:
            return jsonify({'error': 'Failed to generate outfit'}), 500

        return jsonify(outfit.to_dict()), 200

    except Exception as e:
        logger.error(f"Error generating outfit: {str(e)}")
        return jsonify({'error': str(e)}), 500


@fabric_api.route('/outfits/generate-variants', methods=['POST'])
@require_openai
@async_route
async def generate_outfit_variants():
    """
    Generate multiple outfit variants.

    Body: Same as /outfits/generate plus:
        {
            "num_variants": 3
        }
    """
    try:
        data = request.get_json()

        if not data or 'occasion' not in data or 'season' not in data:
            return jsonify({'error': 'occasion and season required'}), 400

        # Create outfit spec
        spec = OutfitSpec(
            occasion=data['occasion'],
            season=data['season'],
            style_preferences=data.get('style_preferences', ['classic']),
            color_preferences=data.get('color_preferences'),
            pattern_preferences=data.get('pattern_preferences'),
            additional_notes=data.get('additional_notes')
        )

        num_variants = data.get('num_variants', 3)

        # Generate variants
        variants = await outfit_generator.generate_outfit_variants(spec, num_variants=num_variants)

        return jsonify({
            'total': len(variants),
            'variants': [outfit.to_dict() for outfit in variants]
        }), 200

    except Exception as e:
        logger.error(f"Error generating variants: {str(e)}")
        return jsonify({'error': str(e)}), 500


@fabric_api.route('/outfits/showcase/<fabric_code>', methods=['POST'])
@require_database
@require_openai
@async_route
async def generate_fabric_showcase(fabric_code: str):
    """Generate showcase outfit for specific fabric"""
    try:
        # Get fabric from database
        fabric = db_manager.get_fabric_by_code(fabric_code)

        if not fabric:
            return jsonify({'error': 'Fabric not found'}), 404

        # Convert to FabricData for outfit generator
        from temp_review.modules.fabric_scraper import FabricData
        fabric_data = FabricData(
            fabric_code=fabric.fabric_code,
            name=fabric.name,
            composition=fabric.composition,
            weight=fabric.weight,
            color=fabric.color,
            pattern=fabric.pattern,
            season=[s.season for s in fabric.seasons] if fabric.seasons else None,
            category=fabric.category
        )

        # Generate showcase
        outfit = await outfit_generator.generate_fabric_showcase(fabric_data)

        if not outfit:
            return jsonify({'error': 'Failed to generate showcase'}), 500

        return jsonify(outfit.to_dict()), 200

    except Exception as e:
        logger.error(f"Error generating showcase: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Stats and Utilities
# ============================================================================

@fabric_api.route('/stats', methods=['GET'])
@require_database
def get_stats():
    """Get database statistics"""
    try:
        stats = db_manager.get_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


@fabric_api.route('/categories', methods=['GET'])
def get_categories():
    """Get fabric categories"""
    from config.fabric_config import FABRIC_CATEGORIES

    return jsonify({
        'categories': FABRIC_CATEGORIES
    }), 200


# Error handlers
@fabric_api.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request', 'message': str(error)}), 400


@fabric_api.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'message': str(error)}), 404


@fabric_api.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error', 'message': str(error)}), 500


def register_fabric_api(app):
    """
    Register fabric API blueprint with Flask app.

    Usage:
        from modules.fabric_api import register_fabric_api
        register_fabric_api(app)
    """
    app.register_blueprint(fabric_api)
    logger.info("Fabric API registered at /api/fabrics")
