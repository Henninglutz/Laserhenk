"""
CSV Fabric Importer with Image Download
Imports fabrics from Formens CSV export and downloads associated images
"""

import csv
import os
import ssl
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging
from dataclasses import dataclass

from config.fabric_config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


@dataclass
class CSVFabricData:
    """Fabric data from CSV"""
    fabric_code: str
    supplier: str
    origin: str
    composition: str
    weight: Optional[int]
    color: str
    pattern: str
    category: str
    season: str
    stock_status: str

    # Additional fields
    lager: str = ""
    bestellte_menge: str = ""
    empfangsdatum: str = ""
    eigenschaften: str = ""
    katalog: str = ""
    produkttyp: str = ""
    mto: str = ""
    preiskat: str = ""
    fabric_img: str = ""  # Direct image URL from CSV


class FabricCSVImporter:
    """Import fabrics from CSV with image download"""

    # CSV column mapping (German -> English)
    COLUMN_MAPPING = {
        'Stoffcode': 'fabric_code',
        'Stofflieferant': 'supplier',
        'Herstellungsland': 'origin',
        'Zusammensetzung': 'composition',
        'Gewicht': 'weight',
        'Stofffarbe': 'color',
        'Stoffart': 'pattern',
        'Produkttyp': 'produkttyp',
        'Saison': 'season',
        'Status': 'stock_status',
        'Lager': 'lager',
        'Bestellte Menge': 'bestellte_menge',
        'Voraussichtliches Empfangsdatum': 'empfangsdatum',
        'Eigenschaften': 'eigenschaften',
        'Katalog': 'katalog',
        'MTO': 'mto',
        'Preiskat': 'preiskat'
    }

    # Category mapping based on Produkttyp
    CATEGORY_MAPPING = {
        'Anzug': 'Business Suits',
        'Smoking': 'Ceremony Suits',
        'Freizeit': 'Casual Wear',
        'Sommer': 'Seasonal',
        'Winter': 'Seasonal'
    }

    # Image URL patterns
    IMAGE_CATEGORIES = ['Ceremony Suits', 'Business Suits', 'Casual Wear', 'Seasonal']
    IMAGE_URL_PATTERN = "https://b2b2.formens.ro/documente/marketing/{category}/05._{code}.jpg"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.downloaded_images: List[str] = []
        self.failed_images: List[str] = []

    async def __aenter__(self):
        """Async context manager entry"""
        # Create SSL context that doesn't verify certificates (for Mac compatibility)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def parse_weight(self, weight_str: str) -> Optional[int]:
        """Parse weight string like '250 g/m²' to integer"""
        if not weight_str:
            return None
        try:
            # Extract number from string like "250 g/m²"
            import re
            match = re.search(r'(\d+)', weight_str)
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    def extract_fabric_name(self, fabric_code: str) -> str:
        """Extract fabric name from code for display purposes"""
        import re
        letters = re.findall(r'[A-Z]+', fabric_code)
        if letters:
            return letters[0]
        return ""

    def convert_fabric_code_for_url(self, fabric_code: str) -> str:
        """Convert fabric code to image URL format
        Examples:
        - '695.401/18' -> '695.401_18'
        - '65C4034' -> '65C4034'
        """
        return fabric_code.replace('/', '_')

    def extract_fabric_name(self, fabric_code: str) -> str:
        """Extract fabric name from code (e.g., 'VITALE' from '695.401/18')"""
        # Try to extract letters from the code
        import re
        # Pattern: extract uppercase letters that might be the fabric name
        # For codes like "586.861/122" we might not have a name, use supplier
        letters = re.findall(r'[A-Z]+', fabric_code)
        if letters:
            return letters[0]
        return ""

    def map_category(self, produkttyp: str) -> str:
        """Map Produkttyp to Formens category"""
        return self.CATEGORY_MAPPING.get(produkttyp, 'Business Suits')

    def read_csv(self, csv_path: str) -> List[CSVFabricData]:
        """Read and parse CSV file"""
        logger.info(f"Reading CSV from {csv_path}")
        fabrics = []

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')  # Formens CSV uses semicolon

                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Map columns
                        fabric_data = {}
                        for csv_col, data_field in self.COLUMN_MAPPING.items():
                            fabric_data[data_field] = row.get(csv_col, '').strip()

                        # Parse weight
                        weight = self.parse_weight(fabric_data.get('weight', ''))

                        # Map category
                        category = self.map_category(fabric_data.get('produkttyp', ''))

                        # Create fabric object
                        fabric = CSVFabricData(
                            fabric_code=fabric_data.get('fabric_code', ''),
                            supplier=fabric_data.get('supplier', ''),
                            origin=fabric_data.get('origin', ''),
                            composition=fabric_data.get('composition', ''),
                            weight=weight,
                            color=fabric_data.get('color', ''),
                            pattern=fabric_data.get('pattern', ''),
                            category=category,
                            season=fabric_data.get('season', ''),
                            stock_status=fabric_data.get('stock_status', ''),
                            lager=fabric_data.get('lager', ''),
                            bestellte_menge=fabric_data.get('bestellte_menge', ''),
                            empfangsdatum=fabric_data.get('empfangsdatum', ''),
                            eigenschaften=fabric_data.get('eigenschaften', ''),
                            katalog=fabric_data.get('katalog', ''),
                            produkttyp=fabric_data.get('produkttyp', ''),
                            mto=fabric_data.get('mto', ''),
                            preiskat=fabric_data.get('preiskat', '')
                        )

                        if fabric.fabric_code:  # Only add if we have a code
                            fabrics.append(fabric)

                    except Exception as e:
                        logger.warning(f"Error parsing row {row_num}: {e}")
                        continue

            logger.info(f"Successfully parsed {len(fabrics)} fabrics from CSV")
            return fabrics

        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            raise

    def construct_image_urls(self, fabric: CSVFabricData) -> List[str]:
        """Construct potential image URLs for a fabric"""
        urls = []

        # PRIORITY 1: Use direct image URL from CSV if available
        if fabric.fabric_img and fabric.fabric_img.strip():
            urls.append(fabric.fabric_img.strip())

        # PRIORITY 2: Try b2b2.formens.ro/img/tissu-veste/ path (most common)
        fabric_code_url = self.convert_fabric_code_for_url(fabric.fabric_code)
        direct_img_url = f"https://b2b2.formens.ro/img/tissu-veste/{fabric_code_url}.jpg"
        urls.append(direct_img_url)

        # PRIORITY 3: Construct URLs from documente/marketing path as fallback
        url = self.IMAGE_URL_PATTERN.format(
            category=fabric.category,
            code=fabric_code_url
        )
        urls.append(url)

        # Try all categories as fallback
        for category in self.IMAGE_CATEGORIES:
            if category != fabric.category:
                url = self.IMAGE_URL_PATTERN.format(
                    category=category,
                    code=fabric_code_url
                )
                urls.append(url)

        return urls

    async def download_image(self, url: str, fabric_code: str) -> Optional[str]:
        """Download image from URL"""
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()

                    # Save image
                    filename = f"{fabric_code.replace('/', '_')}.jpg"
                    filepath = os.path.join(config.FABRIC_IMAGE_STORAGE, filename)

                    with open(filepath, 'wb') as f:
                        f.write(content)

                    logger.info(f"Downloaded image for {fabric_code}: {url}")
                    self.downloaded_images.append(filepath)
                    return filepath

        except Exception as e:
            logger.debug(f"Failed to download {url}: {e}")

        return None

    async def download_fabric_images(self, fabric: CSVFabricData) -> List[str]:
        """Download all available images for a fabric"""
        urls = self.construct_image_urls(fabric)
        images = []

        for url in urls:
            filepath = await self.download_image(url, fabric.fabric_code)
            if filepath:
                images.append(filepath)
                break  # Stop after first successful download

        if not images:
            logger.warning(f"No images found for fabric {fabric.fabric_code}")
            self.failed_images.append(fabric.fabric_code)

        return images

    async def import_csv(self, csv_path: str) -> Dict:
        """Import fabrics from CSV with image download"""
        logger.info("=" * 70)
        logger.info("FABRIC CSV IMPORT - Starting...")
        logger.info("=" * 70)

        # Read CSV
        fabrics = self.read_csv(csv_path)
        logger.info(f"Found {len(fabrics)} fabrics in CSV")

        # Download images
        logger.info("Downloading images...")
        for i, fabric in enumerate(fabrics, 1):
            logger.info(f"Processing {i}/{len(fabrics)}: {fabric.fabric_code}")
            await self.download_fabric_images(fabric)

            # Rate limiting
            if i % 10 == 0:
                await asyncio.sleep(2)

        # Convert to format compatible with fabric_processor
        fabric_dicts = []
        for fabric in fabrics:
            # Find downloaded images
            images = [img for img in self.downloaded_images
                     if fabric.fabric_code.replace('/', '_') in img]

            fabric_dict = {
                'fabric_code': fabric.fabric_code,
                'name': self.extract_fabric_name(fabric.fabric_code) or fabric.supplier,
                'supplier': fabric.supplier,
                'origin': fabric.origin,
                'composition': fabric.composition,
                'weight': fabric.weight,
                'color': fabric.color,
                'pattern': fabric.pattern,
                'category': fabric.category,
                'seasons': [fabric.season] if fabric.season else [],
                'stock_status': fabric.stock_status,
                'images': images,
                'description': f"{fabric.composition}, {fabric.weight}g/m², {fabric.color}",
                'scrape_date': datetime.now().isoformat(),
                'additional_metadata': {
                    'lager': fabric.lager,
                    'bestellte_menge': fabric.bestellte_menge,
                    'empfangsdatum': fabric.empfangsdatum,
                    'eigenschaften': fabric.eigenschaften,
                    'katalog': fabric.katalog,
                    'produkttyp': fabric.produkttyp,
                    'mto': fabric.mto,
                    'preiskat': fabric.preiskat
                }
            }
            fabric_dicts.append(fabric_dict)

        # Save to JSON
        import json
        output_path = os.path.join(
            config.FABRIC_DATA_STORAGE,
            f"csv_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(fabric_dicts, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(fabric_dicts)} fabrics to {output_path}")

        # Statistics
        stats = {
            'total_fabrics': len(fabrics),
            'images_downloaded': len(self.downloaded_images),
            'images_failed': len(self.failed_images),
            'output_file': output_path
        }

        logger.info("=" * 70)
        logger.info("CSV IMPORT COMPLETE")
        logger.info(f"Total fabrics: {stats['total_fabrics']}")
        logger.info(f"Images downloaded: {stats['images_downloaded']}")
        logger.info(f"Images failed: {stats['images_failed']}")
        logger.info(f"Output: {stats['output_file']}")
        logger.info("=" * 70)

        return stats


async def main(csv_path: str):
    """Main import function"""
    async with FabricCSVImporter() as importer:
        stats = await importer.import_csv(csv_path)
        return stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fabric_csv_importer.py <path_to_csv>")
        print("Example: python fabric_csv_importer.py ~/Schreibtisch/fabrics_export_v1.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    asyncio.run(main(csv_path))