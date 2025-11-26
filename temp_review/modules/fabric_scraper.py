"""
HENK Fabric Scraper
Scrapes fabric data from Formens B2B platform with authentication and rate limiting.
"""

import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential
from PIL import Image
import io

from config.fabric_config import config, FABRIC_CATEGORIES

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


@dataclass
class FabricData:
    """Data structure for fabric information"""
    fabric_code: str
    name: Optional[str] = None
    composition: Optional[str] = None
    weight: Optional[int] = None  # grams per square meter
    color: Optional[str] = None
    pattern: Optional[str] = None
    price_category: Optional[str] = None
    stock_status: Optional[str] = None
    season: Optional[List[str]] = None
    supplier: Optional[str] = "Formens"
    origin: Optional[str] = None
    image_urls: Optional[List[str]] = None
    local_image_paths: Optional[List[str]] = None
    description: Optional[str] = None
    care_instructions: Optional[str] = None
    category: Optional[str] = None
    scrape_date: str = None
    additional_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.scrape_date is None:
            self.scrape_date = datetime.utcnow().isoformat()
        if self.image_urls is None:
            self.image_urls = []
        if self.local_image_paths is None:
            self.local_image_paths = []
        if self.season is None:
            self.season = []
        if self.additional_metadata is None:
            self.additional_metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class FormensScraper:
    """
    Scraper for Formens B2B fabric platform.
    Handles authentication, data extraction, and image downloading.
    """

    def __init__(self):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.authenticated = False
        self.scraped_fabrics: List[FabricData] = []

        # Ensure storage directories exist
        Path(config.FABRIC_IMAGE_STORAGE).mkdir(parents=True, exist_ok=True)
        Path(config.FABRIC_DATA_STORAGE).mkdir(parents=True, exist_ok=True)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def initialize(self):
        """Initialize browser and context"""
        logger.info("Initializing Playwright browser...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=config.SCRAPER_HEADLESS,
            args=['--disable-blink-features=AutomationControlled']
        )

        # Create context with realistic settings
        self.context = await self.browser.new_context(
            user_agent=config.SCRAPER_USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
        )

        # Add stealth settings
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        self.page = await self.context.new_page()
        logger.info("Browser initialized successfully")

    async def close(self):
        """Close browser and cleanup"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def authenticate(self) -> bool:
        """
        Authenticate to Formens B2B platform.
        Returns True if authentication successful.
        """
        try:
            username, password = config.get_formens_credentials()
            logger.info(f"Attempting to authenticate as {username}")

            # Navigate to login page
            await self.page.goto(config.FORMENS_BASE_URL, wait_until="networkidle")
            await self._random_delay()

            # Look for login form - adjust selectors based on actual page structure
            # These are common patterns, may need adjustment after inspecting the actual page
            login_selectors = [
                'input[name="username"]', 'input[name="user"]', 'input[name="email"]',
                'input[type="text"]', '#username', '#user', '#email'
            ]

            password_selectors = [
                'input[name="password"]', 'input[type="password"]',
                '#password', '#pass'
            ]

            # Try to find login form
            username_input = None
            for selector in login_selectors:
                try:
                    username_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if username_input:
                        logger.info(f"Found username field: {selector}")
                        break
                except:
                    continue

            if not username_input:
                # Check if we're already logged in
                current_url = self.page.url
                if "login" not in current_url.lower():
                    logger.info("Appears to be already authenticated")
                    self.authenticated = True
                    return True

                logger.error("Could not find login form")
                return False

            # Fill in credentials
            await username_input.fill(username)
            await self._random_delay(0.5, 1.5)

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if password_input:
                        logger.info(f"Found password field: {selector}")
                        break
                except:
                    continue

            if not password_input:
                logger.error("Could not find password field")
                return False

            await password_input.fill(password)
            await self._random_delay(0.5, 1.5)

            # Submit form
            submit_selectors = [
                'button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Login")', 'button:has-text("Sign in")',
                'button:has-text("Enter")', 'button:has-text("Log in")'
            ]

            for selector in submit_selectors:
                try:
                    submit_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if submit_button:
                        logger.info(f"Found submit button: {selector}")
                        await submit_button.click()
                        break
                except:
                    continue
            else:
                # Try pressing Enter as fallback
                await password_input.press('Enter')

            # Wait for navigation
            await self.page.wait_for_load_state("networkidle", timeout=30000)
            await self._random_delay()

            # Verify authentication
            current_url = self.page.url
            if "login" not in current_url.lower() or "stock" in current_url.lower():
                logger.info("Authentication successful!")
                self.authenticated = True
                return True
            else:
                logger.error("Authentication failed - still on login page")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False

    async def navigate_to_stock_page(self) -> bool:
        """Navigate to the fabric stock page"""
        try:
            if not self.authenticated:
                success = await self.authenticate()
                if not success:
                    return False

            logger.info("Navigating to stock page...")
            await self.page.goto(config.FORMENS_STOCK_URL, wait_until="load", timeout=120000)
            await self._random_delay()

            # Wait for the fabric listings to be visible
            try:
                await self.page.wait_for_selector(".product-item, .fabric-item, .card", timeout=15000)
            except:
                logger.warning("Could not find standard fabric selectors, proceeding anyway")

            logger.info(f"Current URL: {self.page.url}")
            return True

        except Exception as e:
            logger.error(f"Error navigating to stock page: {str(e)}")
            return False

    async def scrape_fabric_listings(self) -> List[FabricData]:
        """
        Scrape all fabric listings from the stock page.
        Returns list of FabricData objects.
        """
        try:
            if not await self.navigate_to_stock_page():
                logger.error("Failed to navigate to stock page")
                return []

            logger.info("Scraping fabric listings...")

            # Wait for content to load
            await self.page.wait_for_load_state("networkidle")

            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'lxml')

            # Save HTML for debugging
            debug_path = Path(config.FABRIC_DATA_STORAGE) / f"page_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            debug_path.write_text(content, encoding='utf-8')
            logger.info(f"Saved page HTML to {debug_path}")

            # Extract fabric listings
            # This is a template - selectors need to be adjusted based on actual page structure
            fabrics = []

            # Common patterns for fabric listings
            fabric_containers = soup.find_all(['div', 'tr', 'article'], class_=re.compile(r'fabric|product|item|row', re.I))

            if not fabric_containers:
                # Try table rows
                fabric_containers = soup.select('table tr')

            logger.info(f"Found {len(fabric_containers)} potential fabric containers")

            for container in fabric_containers:
                try:
                    fabric_data = await self._extract_fabric_data(container, soup)
                    if fabric_data and fabric_data.fabric_code:
                        fabrics.append(fabric_data)
                        logger.info(f"Extracted fabric: {fabric_data.fabric_code}")
                except Exception as e:
                    logger.warning(f"Error extracting fabric data: {str(e)}")
                    continue

            self.scraped_fabrics.extend(fabrics)
            logger.info(f"Successfully scraped {len(fabrics)} fabrics")

            return fabrics

        except Exception as e:
            logger.error(f"Error scraping fabric listings: {str(e)}")
            return []

    async def _extract_fabric_data(self, container, soup) -> Optional[FabricData]:
        """
        Extract fabric data from a container element.
        This is a template method that needs customization based on actual page structure.
        """
        try:
            # Extract fabric code - look for patterns like "34C4054"
            text_content = container.get_text(strip=True)

            # Pattern for fabric codes (alphanumeric, typically 6-8 characters)
            code_match = re.search(r'\b([A-Z0-9]{6,8})\b', text_content)
            if not code_match:
                return None

            fabric_code = code_match.group(1)

            # Extract other data points
            name = self._extract_text(container, ['h1', 'h2', 'h3', 'h4', '.name', '.title'])
            composition = self._extract_text(container, ['.composition', '.material', '.fabric-type'])
            color = self._extract_text(container, ['.color', '.colour'])

            # Extract weight (look for patterns like "250g", "250 g/m2", etc.)
            weight = None
            weight_match = re.search(r'(\d{2,3})\s*g', text_content)
            if weight_match:
                weight = int(weight_match.group(1))

            # Extract image URLs
            image_urls = []
            images = container.find_all('img')
            for img in images:
                src = img.get('src') or img.get('data-src')
                if src:
                    full_url = urljoin(config.FORMENS_BASE_URL, src)
                    image_urls.append(full_url)

            # Try to construct image URL from fabric code pattern
            # Based on example: https://b2b2.formens.ro/documente/marketing/Ceremony%20Suits/05._34C4054.jpg
            if not image_urls:
                # Try different category patterns
                for category in ['Ceremony Suits', 'Business Suits', 'Casual Wear']:
                    constructed_url = f"{config.FORMENS_IMAGE_BASE_URL}/{category}/05._{fabric_code}.jpg"
                    image_urls.append(constructed_url)

            fabric_data = FabricData(
                fabric_code=fabric_code,
                name=name or fabric_code,
                composition=composition,
                weight=weight,
                color=color,
                image_urls=image_urls,
                supplier="Formens",
                scrape_date=datetime.utcnow().isoformat()
            )

            return fabric_data

        except Exception as e:
            logger.warning(f"Error extracting fabric data from container: {str(e)}")
            return None

    def _extract_text(self, container, selectors: List[str]) -> Optional[str]:
        """Helper to extract text from multiple possible selectors"""
        for selector in selectors:
            if selector.startswith('.') or selector.startswith('#'):
                element = container.select_one(selector)
            else:
                element = container.find(selector)

            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None

    async def scrape_fabric_details(self, fabric: FabricData) -> FabricData:
        """
        Scrape detailed information for a specific fabric.
        Navigate to detail page if available.
        """
        try:
            logger.info(f"Scraping details for fabric {fabric.fabric_code}")

            # If fabric has a detail page URL, navigate to it
            # This would need to be implemented based on actual site structure

            # For now, enhance with image verification
            fabric = await self._verify_and_download_images(fabric)

            return fabric

        except Exception as e:
            logger.error(f"Error scraping fabric details: {str(e)}")
            return fabric

    async def _verify_and_download_images(self, fabric: FabricData) -> FabricData:
        """Verify image URLs and download images"""
        verified_urls = []
        local_paths = []

        async with aiohttp.ClientSession() as session:
            for url in fabric.image_urls:
                try:
                    async with session.head(url, timeout=10) as response:
                        if response.status == 200:
                            verified_urls.append(url)

                            # Download image
                            local_path = await self._download_image(url, fabric.fabric_code, session)
                            if local_path:
                                local_paths.append(local_path)
                        else:
                            logger.warning(f"Image not accessible: {url} (status {response.status})")
                except Exception as e:
                    logger.warning(f"Error verifying image {url}: {str(e)}")
                    continue

        fabric.image_urls = verified_urls
        fabric.local_image_paths = local_paths

        if not verified_urls:
            logger.warning(f"No valid images found for fabric {fabric.fabric_code}")

        return fabric

    async def _download_image(self, url: str, fabric_code: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Download and optimize fabric image"""
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None

                image_data = await response.read()

                # Process image
                image = Image.open(io.BytesIO(image_data))

                # Resize if too large
                if image.width > config.IMAGE_MAX_WIDTH or image.height > config.IMAGE_MAX_HEIGHT:
                    image.thumbnail((config.IMAGE_MAX_WIDTH, config.IMAGE_MAX_HEIGHT), Image.Resampling.LANCZOS)

                # Convert to RGB if necessary
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background

                # Save image
                filename = f"{fabric_code}_{urlparse(url).path.split('/')[-1]}"
                filename = re.sub(r'[^\w\-_.]', '_', filename)
                if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    filename += '.jpg'

                local_path = Path(config.FABRIC_IMAGE_STORAGE) / filename
                image.save(local_path, config.IMAGE_FORMAT, quality=config.IMAGE_QUALITY, optimize=True)

                logger.info(f"Downloaded image: {local_path}")
                return str(local_path)

        except Exception as e:
            logger.error(f"Error downloading image {url}: {str(e)}")
            return None

    async def scrape_all_fabrics(self, max_fabrics: Optional[int] = None) -> List[FabricData]:
        """
        Main method to scrape all fabrics with details.

        Args:
            max_fabrics: Maximum number of fabrics to scrape (None for all)

        Returns:
            List of FabricData objects
        """
        try:
            # Get fabric listings
            fabrics = await self.scrape_fabric_listings()

            if max_fabrics:
                fabrics = fabrics[:max_fabrics]

            # Scrape details for each fabric in batches
            detailed_fabrics = []
            batch_size = config.SCRAPER_BATCH_SIZE

            for i in range(0, len(fabrics), batch_size):
                batch = fabrics[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(fabrics)-1)//batch_size + 1}")

                tasks = [self.scrape_fabric_details(fabric) for fabric in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, FabricData):
                        detailed_fabrics.append(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Error in batch processing: {str(result)}")

                # Rate limiting between batches
                await self._random_delay(2, 5)

            # Save results
            self._save_scraped_data(detailed_fabrics)

            return detailed_fabrics

        except Exception as e:
            logger.error(f"Error in scrape_all_fabrics: {str(e)}")
            return []

    def _save_scraped_data(self, fabrics: List[FabricData]):
        """Save scraped fabric data to JSON file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = Path(config.FABRIC_DATA_STORAGE) / f"fabrics_{timestamp}.json"

            data = {
                'scrape_date': datetime.utcnow().isoformat(),
                'total_fabrics': len(fabrics),
                'fabrics': [fabric.to_dict() for fabric in fabrics]
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(fabrics)} fabrics to {output_file}")

            # Also save latest.json for easy access
            latest_file = Path(config.FABRIC_DATA_STORAGE) / "fabrics_latest.json"
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error saving scraped data: {str(e)}")

    async def _random_delay(self, min_seconds: Optional[float] = None, max_seconds: Optional[float] = None):
        """Add random delay to mimic human behavior"""
        min_seconds = min_seconds or config.SCRAPER_DELAY_MIN
        max_seconds = max_seconds or config.SCRAPER_DELAY_MAX
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)


async def main():
    """Example usage"""
    async with FormensScraper() as scraper:
        # Authenticate
        success = await scraper.authenticate()
        if not success:
            logger.error("Failed to authenticate")
            return

        # Scrape fabrics
        fabrics = await scraper.scrape_all_fabrics(max_fabrics=10)  # Limit to 10 for testing

        logger.info(f"Scraped {len(fabrics)} fabrics")
        for fabric in fabrics[:3]:  # Show first 3
            logger.info(f"\n{fabric.to_json()}")


if __name__ == "__main__":
    asyncio.run(main())
