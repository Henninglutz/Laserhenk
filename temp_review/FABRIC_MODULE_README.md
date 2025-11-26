# HENK Fabric Scraping & RAG Integration Module

Complete implementation of fabric data collection, processing, and intelligent recommendation system for HENK AI-powered bespoke men's tailoring.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)

## Overview

This module provides:

1. **Web Scraping**: Automated fabric data collection from Formens B2B platform
2. **RAG System**: Vector embeddings and semantic search for intelligent fabric recommendations
3. **DALL-E Integration**: AI-generated outfit visualizations based on fabric data
4. **API**: RESTful endpoints for frontend consumption
5. **Database**: PostgreSQL with pgvector for efficient similarity search

## Architecture

```
henk/
├── modules/
│   ├── fabric_scraper.py      # Web scraping with Playwright
│   ├── fabric_processor.py    # Data processing & RAG
│   ├── outfit_generator.py    # DALL-E integration
│   └── fabric_api.py          # REST API endpoints
├── database/
│   ├── models.py              # SQLAlchemy models
│   ├── db_manager.py          # Database operations
│   └── fabric_migrations.sql  # Schema migrations
├── config/
│   └── fabric_config.py       # Configuration management
├── tests/
│   └── test_fabric_module.py  # Unit tests
└── storage/
    └── fabrics/
        ├── images/            # Downloaded fabric images
        └── data/              # Scraped JSON data
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Set Up PostgreSQL with pgvector

```bash
# Install PostgreSQL (if not already installed)
# On Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# Create database
createdb henk_fabrics

# Run migrations
psql henk_fabrics < database/fabric_migrations.sql
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in required values:

```bash
cp .env.example .env
```

Required variables:
```env
# Formens B2B Credentials
FORMENS_USERNAME=your_username
FABRIC_SCRAPER_PASSWORD=your_password

# OpenAI API
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/henk_fabrics
```

## Configuration

All configuration is managed in `config/fabric_config.py` using Pydantic for validation.

### Key Settings

```python
from config.fabric_config import config

# Scraping settings
config.SCRAPER_DELAY_MIN = 1.0  # Min delay between requests
config.SCRAPER_BATCH_SIZE = 10  # Parallel processing batch size

# RAG settings
config.RAG_TOP_K_RESULTS = 5    # Number of similar results
config.RAG_SIMILARITY_THRESHOLD = 0.7  # Min similarity score

# OpenAI settings
config.OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
config.OPENAI_DALLE_MODEL = "dall-e-3"
```

### Fabric Categories

Pre-defined categories in `config/fabric_config.py`:

- **Ceremony Suits**: Wedding, formal events
- **Business Suits**: Professional attire
- **Casual Wear**: Smart casual, weekend
- **Seasonal Collections**: Special collections

## Usage

### 1. Scrape Fabric Data

```python
import asyncio
from temp_review.modules.fabric_scraper import FormensScraper


async def scrape_fabrics():
    async with FormensScraper() as scraper:
        # Authenticate
        await scraper.authenticate()

        # Scrape all fabrics
        fabrics = await scraper.scrape_all_fabrics(max_fabrics=50)

        print(f"Scraped {len(fabrics)} fabrics")


asyncio.run(scrape_fabrics())
```

Or use the command-line interface:

```bash
python modules/fabric_scraper.py
```

### 2. Process Data for RAG

```python
import asyncio
from pathlib import Path
from temp_review.modules.fabric_processor import FabricProcessor
from temp_review.modules.fabric_scraper import FabricData


async def process_fabrics():
    processor = FabricProcessor()

    # Load scraped data
    with open('storage/fabrics/data/fabrics_latest.json', 'r') as f:
        data = json.load(f)

    fabrics = [FabricData(**f) for f in data['fabrics']]

    # Process and generate embeddings
    chunks = await processor.process_batch(fabrics)

    # Save processed data
    processor.save_processed_data(chunks)


asyncio.run(process_fabrics())
```

Or use the command-line interface:

```bash
python modules/fabric_processor.py
```

### 3. Import to Database

```python
from database.db_manager import DatabaseManager
from pathlib import Path

db = DatabaseManager()

# Create tables
db.create_tables()

# Import fabric data
db.import_from_json(Path('storage/fabrics/data/fabrics_latest.json'))

# Import embeddings
db.import_embeddings_from_json(Path('storage/fabrics/data/processed_latest.json'))

# Check stats
print(db.get_stats())
```

Or use the command-line interface:

```bash
python database/db_manager.py
```

### 4. Generate Outfit Visualizations

```python
import asyncio
from temp_review.modules.outfit_generator import OutfitGenerator, OutfitSpec


async def generate_outfit():
    generator = OutfitGenerator()

    # Define outfit specification
    spec = OutfitSpec(
        occasion='wedding',
        season='summer',
        style_preferences=['classic', 'elegant'],
        color_preferences=['navy', 'light blue'],
        pattern_preferences=['solid'],
        additional_notes='For outdoor summer ceremony'
    )

    # Generate outfit with RAG fabric selection
    outfit = await generator.generate_outfit(spec, use_rag=True)

    print(f"Generated outfit: {outfit.outfit_id}")
    print(f"Image saved to: {outfit.local_image_path}")
    print(f"Fabrics used: {outfit.fabrics_used}")


asyncio.run(generate_outfit())
```

### 5. Integrate with Flask App

Update `app.py` to register the fabric API:

```python
from flask import Flask
from temp_review.modules.fabric_api import register_fabric_api

app = Flask(__name__)

# Register fabric API
register_fabric_api(app)

# ... rest of your app code
```

## API Endpoints

### Base URL: `/api/fabrics`

#### Health Check

```http
GET /api/fabrics/health
```

Returns system status and configuration.

#### Get All Fabrics

```http
GET /api/fabrics/?limit=10&category=business&season=summer
```

Query parameters:
- `limit` (optional): Max results
- `category` (optional): Filter by category
- `season` (optional): Filter by season
- `color` (optional): Filter by color
- `pattern` (optional): Filter by pattern

#### Get Specific Fabric

```http
GET /api/fabrics/34C4054
```

Returns detailed fabric information including images and seasons.

#### Search Fabrics (RAG)

```http
POST /api/fabrics/search
Content-Type: application/json

{
  "query": "lightweight summer fabric for wedding",
  "limit": 5,
  "threshold": 0.7
}
```

Returns semantically similar fabrics using vector search.

#### Recommend Fabrics

```http
POST /api/fabrics/recommend
Content-Type: application/json

{
  "occasion": "wedding",
  "season": "summer",
  "style_preferences": ["classic", "elegant"],
  "color_preferences": ["navy", "light blue"],
  "pattern_preferences": ["solid"],
  "limit": 3
}
```

Returns personalized fabric recommendations based on preferences.

#### Generate Outfit

```http
POST /api/fabrics/outfits/generate
Content-Type: application/json

{
  "occasion": "wedding",
  "season": "summer",
  "style_preferences": ["classic", "elegant"],
  "color_preferences": ["navy", "light blue"],
  "pattern_preferences": ["solid"],
  "fabric_codes": ["34C4054"],
  "additional_notes": "For outdoor ceremony",
  "use_rag": true
}
```

Generates DALL-E outfit visualization.

#### Generate Outfit Variants

```http
POST /api/fabrics/outfits/generate-variants
Content-Type: application/json

{
  "occasion": "wedding",
  "season": "summer",
  "num_variants": 3
}
```

Generates multiple outfit variations.

#### Fabric Showcase

```http
POST /api/fabrics/outfits/showcase/34C4054
```

Generates showcase outfit for specific fabric.

#### Get Statistics

```http
GET /api/fabrics/stats
```

Returns database statistics (total fabrics, embeddings, etc.).

#### Get Categories

```http
GET /api/fabrics/categories
```

Returns available fabric categories and their properties.

## Database Schema

### Core Tables

- **fabrics**: Main fabric information
- **fabric_seasons**: Fabric to season mapping (many-to-many)
- **fabric_images**: Fabric images and storage info
- **fabric_categories**: Hierarchical categories
- **fabric_embeddings**: Vector embeddings for RAG
- **generated_outfits**: DALL-E generated outfits
- **outfit_fabrics**: Outfit to fabric mapping
- **fabric_recommendations**: Recommendation tracking

### Key Features

- **pgvector** for efficient similarity search
- **HNSW indexes** for fast approximate nearest neighbor queries
- **JSONB** for flexible metadata storage
- **Automatic timestamps** with triggers
- **Referential integrity** with foreign keys

### Migrations

Run migrations to set up the database:

```bash
psql your_database < database/fabric_migrations.sql
```

## Development

### Project Structure

```
modules/
├── fabric_scraper.py      # Scraping logic
│   ├── FabricData         # Data model
│   ├── FormensScraper     # Main scraper class
│   └── Authentication     # Login handling
│
├── fabric_processor.py    # Data processing
│   ├── FabricChunk        # Chunk data model
│   ├── FabricProcessor    # Processing logic
│   └── Embedding generation
│
├── outfit_generator.py    # DALL-E integration
│   ├── OutfitSpec         # Outfit specification
│   ├── GeneratedOutfit    # Result model
│   └── OutfitGenerator    # Generation logic
│
└── fabric_api.py          # REST API
    ├── Blueprint setup
    ├── Route handlers
    └── Error handling
```

### Adding New Features

1. **New Fabric Attributes**: Update `FabricData` in `modules/fabric_scraper.py`
2. **New Chunk Types**: Add to `chunk_type` constraint in database schema
3. **New API Endpoints**: Add routes to `modules/fabric_api.py`
4. **New Categories**: Update `FABRIC_CATEGORIES` in `config/fabric_config.py`

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to all public functions
- Use async/await for I/O operations
- Log important operations

## Testing

### Run All Tests

```bash
python -m pytest tests/ -v
```

### Run Specific Test Class

```bash
python -m pytest tests/test_fabric_module.py::TestFabricProcessor -v
```

### Run with Coverage

```bash
python -m pytest tests/ --cov=modules --cov=database --cov-report=html
```

### Manual Testing

Test individual components:

```bash
# Test scraper
python modules/fabric_scraper.py

# Test processor
python modules/fabric_processor.py

# Test outfit generator
python modules/outfit_generator.py

# Test database
python database/db_manager.py
```

## Deployment

### Environment Setup

1. Set up PostgreSQL with pgvector
2. Configure environment variables
3. Install dependencies
4. Run database migrations
5. Install Playwright browsers

### Production Considerations

- Use gunicorn for Flask app
- Set `SCRAPER_HEADLESS=true` for production
- Configure proper logging
- Set up monitoring for scraping jobs
- Use connection pooling for database
- Cache frequently accessed fabric data
- Rate limit API endpoints
- Enable CORS if needed for frontend

### Scheduled Tasks

Set up cron jobs for regular updates:

```bash
# Daily fabric scraping (2 AM)
0 2 * * * /path/to/venv/bin/python /path/to/modules/fabric_scraper.py

# Daily processing (3 AM)
0 3 * * * /path/to/venv/bin/python /path/to/modules/fabric_processor.py

# Import to database (4 AM)
0 4 * * * /path/to/venv/bin/python /path/to/database/db_manager.py
```

### Docker Deployment (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application
COPY .. .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

## Troubleshooting

### Common Issues

**Issue**: Playwright authentication fails

- Check credentials in `.env`
- Try running with `SCRAPER_HEADLESS=false` to debug
- Check website structure hasn't changed

**Issue**: Database connection fails

- Verify `DATABASE_URL` format
- Check PostgreSQL is running
- Ensure pgvector extension is installed

**Issue**: OpenAI API errors

- Verify `OPENAI_API_KEY` is valid
- Check API rate limits
- Ensure sufficient credits

**Issue**: Embeddings not generated

- Check OpenAI configuration
- Verify fabric data has content
- Check chunk creation logic

### Debug Mode

Enable debug logging:

```python
# In .env
LOG_LEVEL=DEBUG
```

View SQL queries:

```python
# In database/db_manager.py
self.engine = create_engine(url, echo=True)
```

## License

Proprietary - HENK

## Support

For issues and questions, contact the development team or create an issue in the repository.

---

**Version**: 1.0.0
**Last Updated**: 2024
**Maintainer**: HENK Development Team
