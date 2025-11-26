"""
HENK Flask Application
Integrated with Fabric Module for AI-powered fabric recommendations and outfit generation.

This is an example of how to integrate the fabric module with your existing Flask app.
To use this, rename to app.py or merge the fabric API registration into your existing app.py
"""

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import csv, os, requests
from dotenv import load_dotenv

# Import fabric module
from modules.fabric_api import register_fabric_api

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# ============================================================================
# Register Fabric API Blueprint
# ============================================================================
# This adds all fabric endpoints under /api/fabrics/
# See modules/fabric_api.py for available endpoints
register_fabric_api(app)


# ============================================================================
# Pipedrive Integration (existing functionality)
# ============================================================================

def send_to_pipedrive(data):
    """
    Send lead data to Pipedrive CRM (optional).
    Returns True if successful, False otherwise.
    """
    api_token = os.getenv('PIPEDRIVE_API_TOKEN')
    domain = os.getenv('PIPEDRIVE_DOMAIN')

    # Skip if Pipedrive is not configured
    if not api_token or not domain:
        return False

    try:
        base_url = f'https://{domain}.pipedrive.com/api/v1'
        params = {'api_token': api_token}

        # Step 1: Create Person in Pipedrive
        person_data = {
            'name': data.get('name') or data.get('email', 'Beta User'),
            'email': [{'value': data.get('email'), 'primary': True, 'label': 'work'}] if data.get('email') else [],
            'phone': [{'value': data.get('whatsapp'), 'primary': True, 'label': 'mobile'}] if data.get('whatsapp') else []
        }

        person_response = requests.post(
            f'{base_url}/persons',
            params=params,
            json=person_data,
            timeout=10
        )

        if not person_response.ok:
            print(f"Pipedrive Person Error: {person_response.status_code}")
            return False

        person_id = person_response.json().get('data', {}).get('id')

        # Step 2: Create Lead in Pipedrive
        lead_data = {
            'title': f'Beta Anmeldung: {data.get("name") or data.get("email")}',
            'person_id': person_id,
        }

        lead_response = requests.post(
            f'{base_url}/leads',
            params=params,
            json=lead_data,
            timeout=10
        )

        if not lead_response.ok:
            print(f"Pipedrive Lead Error: {lead_response.status_code}")
            return False

        lead_id = lead_response.json().get('data', {}).get('id')

        # Step 3: Create Note for the Lead (note field is deprecated in Leads API)
        note_content = f"Use Case: {data.get('usecase')}\n\nQuelle: Better Call HENK Beta Landing Page" if data.get('usecase') else 'Quelle: Better Call HENK Beta Landing Page'

        note_data = {
            'content': note_content,
            'lead_id': lead_id,
            'pinned_to_lead_flag': 1
        }

        note_response = requests.post(
            f'{base_url}/notes',
            params=params,
            json=note_data,
            timeout=10
        )

        if note_response.ok:
            print(f"✓ Pipedrive Lead + Note created for {data.get('email')}")
            return True
        else:
            print(f"⚠ Lead created but Note failed: {note_response.status_code}")
            # Lead is created, so we still return True
            return True

    except Exception as e:
        print(f"Pipedrive Error: {str(e)}")
        return False


# ============================================================================
# Main Application Routes
# ============================================================================

@app.route('/')
def home():
    """Landing page"""
    return render_template('index.html')


@app.post('/api/subscribe')
def subscribe():
    """Beta subscription endpoint (existing functionality)"""
    payload = request.get_json(force=True, silent=True) or {}
    row = {
        'ts': datetime.utcnow().isoformat()+'Z',
        'name': payload.get('name',''),
        'email': payload.get('email',''),
        'whatsapp': payload.get('whatsapp',''),
        'usecase': payload.get('usecase','')
    }

    # Save to CSV (primary storage)
    os.makedirs('storage', exist_ok=True)
    path = os.path.join('storage', 'leads.csv')
    exists = os.path.exists(path)
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not exists: w.writeheader()
        w.writerow(row)

    # Send to Pipedrive (optional, non-blocking)
    send_to_pipedrive(payload)

    return jsonify({'ok': True})


# ============================================================================
# Fabric Module Integration Examples
# ============================================================================
# These are example routes showing how to use the fabric module
# in your application logic. Remove or modify as needed.

@app.route('/api/fabric-recommendations', methods=['POST'])
def get_fabric_recommendations_for_client():
    """
    Example: Get fabric recommendations for a client based on their preferences.
    This could be used in HENK's H3 design phase.
    """
    try:
        from modules.fabric_processor import FabricProcessor
        from pathlib import Path
        import asyncio

        data = request.get_json()

        # Extract client preferences
        occasion = data.get('occasion', 'business')
        season = data.get('season', 'spring')
        style = data.get('style', 'classic')

        # Build search query
        query = f"{occasion} {season} {style} fabric"

        async def search():
            processor = FabricProcessor()

            # Load processed data
            processed_path = Path('storage/fabrics/data/processed_latest.json')
            if not processed_path.exists():
                return []

            chunks = processor.load_processed_data(processed_path)

            # Search
            results = await processor.similarity_search(
                query=query,
                chunks=chunks,
                top_k=5
            )

            return [
                {
                    'fabric_code': chunk.fabric_code,
                    'content': chunk.content,
                    'score': score,
                    'chunk_type': chunk.chunk_type
                }
                for chunk, score in results
            ]

        results = asyncio.run(search())

        return jsonify({
            'query': query,
            'recommendations': results
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-client-outfit', methods=['POST'])
def generate_client_outfit():
    """
    Example: Generate outfit visualization for a client.
    This could be used in HENK's H3 design phase.
    """
    try:
        from modules.outfit_generator import OutfitGenerator, OutfitSpec
        import asyncio

        data = request.get_json()

        async def generate():
            generator = OutfitGenerator()

            spec = OutfitSpec(
                occasion=data.get('occasion', 'business'),
                season=data.get('season', 'spring'),
                style_preferences=data.get('style_preferences', ['classic']),
                color_preferences=data.get('color_preferences'),
                pattern_preferences=data.get('pattern_preferences'),
                additional_notes=data.get('notes')
            )

            outfit = await generator.generate_outfit(spec, use_rag=True)

            if outfit:
                return outfit.to_dict()
            return None

        result = asyncio.run(generate())

        if result:
            return jsonify(result), 200
        else:
            return jsonify({'error': 'Failed to generate outfit'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Health Check & Info
# ============================================================================

@app.route('/api/health')
def health():
    """
    Application health check.
    Shows status of all components including fabric module.
    """
    from config.fabric_config import config as fabric_config

    status = {
        'status': 'healthy',
        'version': '1.0.0',
        'components': {
            'pipedrive': {
                'configured': bool(os.getenv('PIPEDRIVE_API_TOKEN'))
            },
            'fabric_module': {
                'configured': True,
                'database': fabric_config.is_database_configured(),
                'openai': fabric_config.is_openai_configured(),
                'scraping_enabled': fabric_config.ENABLE_SCRAPING,
                'rag_enabled': fabric_config.ENABLE_RAG,
                'dalle_enabled': fabric_config.ENABLE_DALLE
            }
        }
    }

    # Get fabric module stats if database is configured
    if fabric_config.is_database_configured():
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            status['components']['fabric_module']['stats'] = db.get_stats()
        except Exception as e:
            status['components']['fabric_module']['database_error'] = str(e)

    return jsonify(status), 200


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == '__main__':
    # Print available routes on startup
    print("\n" + "="*80)
    print("HENK Application Starting")
    print("="*80)
    print("\nAvailable Routes:")
    print("\nMain Application:")
    print("  GET  /                              - Landing page")
    print("  POST /api/subscribe                 - Beta subscription")
    print("  GET  /api/health                    - Health check")
    print("\nFabric Module API:")
    print("  GET  /api/fabrics/health            - Fabric module status")
    print("  GET  /api/fabrics/                  - List all fabrics")
    print("  GET  /api/fabrics/<code>            - Get specific fabric")
    print("  POST /api/fabrics/search            - Semantic fabric search (RAG)")
    print("  POST /api/fabrics/recommend         - Get fabric recommendations")
    print("  POST /api/fabrics/outfits/generate  - Generate outfit with DALL-E")
    print("  GET  /api/fabrics/stats             - Database statistics")
    print("\nExample Integration:")
    print("  POST /api/fabric-recommendations    - Client fabric recommendations")
    print("  POST /api/generate-client-outfit    - Client outfit generation")
    print("\n" + "="*80)
    print(f"Server running on http://localhost:8080")
    print("="*80 + "\n")

    app.run(debug=True, port=8080)
