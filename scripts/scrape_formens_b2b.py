"""Scrape fabric data from the Formens B2B portal (b2b2.formens.ro).

The portal hosts ~1988 fabrics but many entries currently miss crucial
metadata such as composition, origin, or the price category. This script
captures a complete fabric catalog including images so that the data can be
re-imported into the HENK database and used for RAG and DALL·E prompts.

The scraper is intentionally defensive because the portal HTML can change
frequently. It focuses on the following:
- Logging in with email/password or an existing session cookie
- Discovering fabric detail links from paginated listing pages
- Extracting detailed attributes from JSON-LD, definition lists, and tables
- Downloading the primary fabric image alongside metadata
- Saving consolidated JSON in ``storage/fabrics/formens_fabrics.json``

Example:
    python scripts/scrape_formens_b2b.py \
        --email "$FORMENS_EMAIL" --password "$FORMENS_PASSWORD" \
        --output-dir storage/fabrics --max-pages 120

You can also pass an authenticated cookie (copied from the browser) via
``--cookie`` if form-based login fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_BASE_URL = "https://b2b2.formens.ro"
DEFAULT_LISTING_PATH = "/fabric"
DEFAULT_LOGIN_PATH = "/auth/login"


@dataclass
class FabricRecord:
    """Normalized fabric payload for downstream imports."""

    code: str
    name: Optional[str]
    url: str
    image_url: Optional[str]
    image_path: Optional[str]
    price_category: Optional[str] = None
    composition: Optional[str] = None
    weight: Optional[str] = None
    origin: Optional[str] = None
    description: Optional[str] = None
    extra: dict = field(default_factory=dict)
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class FormensScraper:
    """HTML scraper for the Formens B2B fabric catalog."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        listing_path: str = DEFAULT_LISTING_PATH,
        login_path: str = DEFAULT_LOGIN_PATH,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session_cookie: Optional[str] = None,
        allow_anonymous: bool = False,
        output_dir: Path = Path("storage/fabrics"),
        sleep_seconds: float = 0.7,
        max_pages: int = 120,
        page_param: str = "page",
        download_images: bool = True,
        verify_tls: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.listing_path = listing_path
        self.login_path = login_path
        self.email = email
        self.username = username
        self.password = password
        self.session_cookie = session_cookie
        self.output_dir = output_dir
        self.images_dir = output_dir / "images"
        self.sleep_seconds = sleep_seconds
        self.max_pages = max_pages
        self.page_param = page_param
        self.download_images = download_images
        self.verify_tls = verify_tls
        self.allow_anonymous = allow_anonymous

        self.session = requests.Session()
        self.session.verify = verify_tls

        # Set browser-like headers to avoid blocks
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7,ro;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        if session_cookie:
            self.session.headers.update({"Cookie": session_cookie})

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Log in using the provided credentials if available.

        The portal expects an email/password POST. This method first loads the
        homepage to discover the actual login form and URL, then submits credentials.
        """

        if self.session_cookie:
            print("ℹ️  Using provided session cookie (skipping form login).")
            return

        if (not self.email and not self.username) or not self.password:
            if self.allow_anonymous:
                print("⚠️  No credentials provided — continuing without login.")
                return
            raise RuntimeError(
                "Login ist erforderlich — nutze --username/--password oder --email/--password "
                "bzw. --cookie (Browser-Session)."
            )

        # Step 1: Load homepage to find login form and URL
        print(f"🔍 Loading homepage to find login form...")
        try:
            homepage_resp = self.session.get(self.base_url, timeout=15)
            homepage_resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to load homepage: {e}")

        soup = BeautifulSoup(homepage_resp.text, "html.parser")

        # Try to find login form
        login_form = None
        for form in soup.find_all("form"):
            form_text = form.get_text().lower()
            if any(word in form_text for word in ['login', 'password', 'anmeld', 'autentificare']):
                login_form = form
                break

        if not login_form:
            # Try to find login link instead
            login_links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                text = link.get_text().lower()
                if any(word in href or word in text for word in ['login', 'auth', 'signin', 'autentificare']):
                    login_links.append(link['href'])

            if login_links:
                # Load the login page
                login_page_url = login_links[0]
                if not login_page_url.startswith('http'):
                    login_page_url = f"{self.base_url}{login_page_url}" if login_page_url.startswith('/') else f"{self.base_url}/{login_page_url}"

                print(f"🔍 Following login link: {login_page_url}")
                try:
                    login_page_resp = self.session.get(login_page_url, timeout=15)
                    login_page_resp.raise_for_status()
                    soup = BeautifulSoup(login_page_resp.text, "html.parser")
                    login_form = soup.find("form")
                except Exception as e:
                    print(f"⚠️  Failed to load login page: {e}")

        if not login_form:
            # Fallback: try the configured login path
            login_url = f"{self.base_url}{self.login_path}"
            print(f"⚠️  No login form found on homepage, trying configured path: {login_url}")
        else:
            # Extract form action
            action = login_form.get('action', '')
            if not action:
                action = self.login_path
            if action.startswith('http'):
                login_url = action
            elif action.startswith('/'):
                login_url = f"{self.base_url}{action}"
            else:
                login_url = f"{self.base_url}/{action}"

        # Step 2: Build payload from form fields
        login_identifier = self.username or self.email
        payload = {}

        if login_form:
            # Extract all input fields from form
            for inp in login_form.find_all("input"):
                name = inp.get("name")
                if not name:
                    continue
                value = inp.get("value", "")
                input_type = inp.get("type", "").lower()

                # Skip submit buttons
                if input_type in ["submit", "button"]:
                    continue

                payload[name] = value

        # Set credentials in payload
        # Try common field names
        username_fields = ["username", "user", "email", "login", "userid"]
        password_fields = ["password", "pass", "passwd", "pwd"]

        # Set username/email
        username_set = False
        for field in username_fields:
            if field in payload or not payload:
                payload[field] = login_identifier
                username_set = True
                break

        # Set password
        password_set = False
        for field in password_fields:
            if field in payload or not payload:
                payload[field] = self.password
                password_set = True
                break

        # Ensure at least basic fields are set
        if not username_set:
            payload["username"] = login_identifier
            payload["email"] = login_identifier
        if not password_set:
            payload["password"] = self.password

        print(f"🔐 Logging in at {login_url} with {'username' if self.username else 'email'}: {login_identifier}")
        print(f"   Form fields: {list(payload.keys())}")

        try:
            resp = self.session.post(login_url, data=payload, timeout=15, allow_redirects=True)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Login failed with status {resp.status_code}: {resp.text[:300]}"
                )

            # Check if we're still on a login page
            if 'password' in resp.text.lower() and ('login' in resp.text.lower() or 'autentificare' in resp.text.lower()):
                # Look for error messages
                error_soup = BeautifulSoup(resp.text, "html.parser")
                error_msgs = []
                for elem in error_soup.find_all(['div', 'span', 'p'], class_=re.compile('error|alert|warning', re.I)):
                    msg = elem.get_text(strip=True)
                    if msg:
                        error_msgs.append(msg)

                error_info = f" Errors: {'; '.join(error_msgs[:3])}" if error_msgs else ""
                raise RuntimeError(
                    f"Login failed — still on login page after POST.{error_info} "
                    f"Check credentials and form fields."
                )

            print("✅ Login successful (session cookies stored).")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Login request failed: {e}")

    # ------------------------------------------------------------------
    # Listing discovery
    # ------------------------------------------------------------------
    def fetch_listing_urls(self) -> list[str]:
        """Walk paginated listings and return unique fabric detail URLs."""

        discovered: list[str] = []
        seen: set[str] = set()

        # Try to find the correct listing path on first page
        if self.listing_path == DEFAULT_LISTING_PATH:
            listing_path = self._find_listing_path()
            if listing_path:
                self.listing_path = listing_path
                print(f"ℹ️  Using discovered listing path: {self.listing_path}")

        for page in range(1, self.max_pages + 1):
            listing_url = self._build_listing_url(page)
            print(f"🌐 Listing page {page}: {listing_url}")

            try:
                resp = self.session.get(listing_url, timeout=15)
            except Exception as e:
                print(f"❌ Request failed: {e}")
                break

            if resp.status_code >= 400:
                if page == 1:
                    # Try alternative paths on first page
                    alternative_found = False
                    for alt_path in ['/fabrics', '/stocktisue', '/products', '/catalog', '/stoffe']:
                        print(f"  Trying alternative: {alt_path}")
                        alt_url = f"{self.base_url}{alt_path}?page=1"
                        try:
                            alt_resp = self.session.get(alt_url, timeout=15)
                            if alt_resp.status_code == 200:
                                print(f"  ✅ Found working listing path: {alt_path}")
                                self.listing_path = alt_path
                                resp = alt_resp
                                listing_url = alt_url
                                alternative_found = True
                                break
                        except Exception:
                            continue

                    if not alternative_found:
                        if self._should_require_auth(resp):
                            raise RuntimeError(
                                "Listing fetch failed (likely not authenticated). "
                                "Provide --email/--password or --cookie; "
                                f"status={resp.status_code}, url={resp.url}"
                            )
                        print(f"⚠️  All listing paths failed with {resp.status_code}.")
                        break
                else:
                    print(f"⚠️  Stopping pagination — got {resp.status_code} on page {page}.")
                    break

            if self._looks_like_login_page(resp):
                raise RuntimeError(
                    "Received a login page instead of listings. Pass --email/--password "
                    "or --cookie (browser session)."
                )

            new_links = self._parse_listing(resp.text)
            new_links = [link for link in new_links if link not in seen]
            if not new_links:
                print("ℹ️  No new product links found — pagination complete.")
                break

            discovered.extend(new_links)
            seen.update(new_links)
            print(f"  ➕ Added {len(new_links)} new links (total {len(discovered)}).")
            time.sleep(self.sleep_seconds)

        return discovered

    def _find_listing_path(self) -> Optional[str]:
        """Try to discover the correct listing path from the homepage or navigation."""
        try:
            resp = self.session.get(self.base_url, timeout=15)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for links that might lead to product listings
            candidates = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().lower()

                # Check if link looks like a product listing
                if any(word in href.lower() or word in text for word in
                       ['fabric', 'stof', 'tisue', 'product', 'catalog', 'catalogue']):
                    # Normalize href
                    if href.startswith('http'):
                        if self.base_url in href:
                            href = href.replace(self.base_url, '')
                        else:
                            continue
                    if not href.startswith('/'):
                        href = '/' + href
                    # Remove query params for now
                    href = href.split('?')[0]
                    candidates.append(href)

            # Return most promising candidate
            if candidates:
                # Prefer shorter paths (usually the main listing)
                candidates.sort(key=len)
                return candidates[0]

        except Exception:
            pass

        return None

    def _build_listing_url(self, page: int) -> str:
        if self.page_param in self.listing_path:
            # Caller already injected the placeholder (e.g., "?page={page}").
            return f"{self.base_url}{self.listing_path.format(page=page)}"

        separator = "&" if "?" in self.listing_path else "?"
        return f"{self.base_url}{self.listing_path}{separator}{self.page_param}={page}"

    def _parse_listing(self, html: str) -> list[str]:
        """Extract product detail links from a listing page."""

        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.find_all("a", href=True)
        detail_links: set[str] = set()

        for anchor in anchors:
            href: str = anchor["href"]
            if not href or href.startswith("#"):
                continue

            # Normalize relative links
            if href.startswith("/"):
                full_url = f"{self.base_url}{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = f"{self.base_url}/{href}"

            if self._is_fabric_detail_link(full_url):
                detail_links.add(full_url)

        return sorted(detail_links)

    def _should_require_auth(self, resp: requests.Response) -> bool:
        if self.allow_anonymous:
            return False
        return resp.status_code in {401, 403, 404}

    def _looks_like_login_page(self, resp: requests.Response) -> bool:
        if self.allow_anonymous:
            return False
        login_tokens = ["<form", "password", "remember", "login", "sign in"]
        body = resp.text.lower()
        return any(token in body for token in login_tokens) or (
            self.login_path.strip("/") in resp.url
        )

    @staticmethod
    def _is_fabric_detail_link(url: str) -> bool:
        patterns = [
            r"/fabric/",
            r"fabric_id",
            r"/fabrics/",
            r"/products/",
        ]
        return any(re.search(pat, url, flags=re.IGNORECASE) for pat in patterns)

    # ------------------------------------------------------------------
    # Detail parsing
    # ------------------------------------------------------------------
    def scrape_fabric(self, url: str) -> FabricRecord:
        """Fetch a fabric detail page and extract metadata."""

        resp = self.session.get(url)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Failed to fetch fabric detail ({resp.status_code}) for {url}"
            )

        soup = BeautifulSoup(resp.text, "html.parser")
        ld_json = self._extract_ld_json(soup)
        image_url = self._extract_image_url(ld_json, soup)
        name = ld_json.get("name") if ld_json else None
        code = self._extract_fabric_code(ld_json, soup)
        description = ld_json.get("description") if ld_json else None

        metadata = self._extract_labeled_metadata(soup)

        record = FabricRecord(
            code=code or url,
            name=name,
            url=url,
            image_url=image_url,
            image_path=None,
            price_category=metadata.get("price_category"),
            composition=metadata.get("composition"),
            weight=metadata.get("weight"),
            origin=metadata.get("origin"),
            description=description,
            extra={
                "care": metadata.get("care"),
                "color": metadata.get("color"),
                "season": metadata.get("season"),
                "supplier": metadata.get("supplier"),
            },
        )

        if self.download_images and record.image_url:
            record.image_path = self._download_image(record.code, record.image_url)

        print(f"  ✅ Scraped {record.code} — {record.name or 'Unnamed fabric'}")
        time.sleep(self.sleep_seconds)
        return record

    @staticmethod
    def _extract_ld_json(soup: BeautifulSoup) -> dict:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except json.JSONDecodeError:
                continue

            if isinstance(data, dict) and data.get("@type") in {"Product", "Offer"}:
                return data
        return {}

    @staticmethod
    def _extract_image_url(ld_json: dict, soup: BeautifulSoup) -> Optional[str]:
        if ld_json:
            image = ld_json.get("image")
            if isinstance(image, list):
                return image[0]
            if isinstance(image, str):
                return image

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]

        fallback = soup.find("img")
        if fallback and fallback.get("src"):
            return fallback["src"]

        return None

    @staticmethod
    def _extract_fabric_code(ld_json: dict, soup: BeautifulSoup) -> Optional[str]:
        if ld_json:
            for key in ("sku", "mpn", "productID"):
                if key in ld_json:
                    return str(ld_json[key])

        patterns = [r"Code[:\s]+(\S+)", r"Fabric[:\s]+(\S+)"]
        text = soup.get_text(" ", strip=True)
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_labeled_metadata(self, soup: BeautifulSoup) -> dict:
        """Capture common attributes from tables, lists, or definition lists."""

        labels = {
            "composition": ["composition", "compozitie"],
            "weight": ["weight", "grammage", "g/m"],
            "origin": ["origin", "made in"],
            "price_category": ["price", "cat", "category"],
            "care": ["care", "washing"],
            "season": ["season", "sezon"],
            "color": ["color", "colour"],
            "supplier": ["supplier", "brand"],
        }

        metadata: dict[str, Optional[str]] = {}
        text_blocks: Iterable[str] = self._iter_labeled_blocks(soup)

        for block in text_blocks:
            for key, tokens in labels.items():
                for token in tokens:
                    if token.lower() in block.lower():
                        value = block.split(":", 1)[-1].strip()
                        if value:
                            metadata.setdefault(key, value)
                        break

        return metadata

    @staticmethod
    def _iter_labeled_blocks(soup: BeautifulSoup) -> Iterable[str]:
        for selector in ("table tr", "dl", "li", "p", "div"):
            for element in soup.select(selector):
                text = element.get_text(" ", strip=True)
                if ":" in text:
                    yield text

    # ------------------------------------------------------------------
    # Image download and persistence
    # ------------------------------------------------------------------
    def _download_image(self, fabric_code: str, image_url: str) -> Optional[str]:
        if not image_url:
            return None

        self.images_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(image_url).suffix or ".jpg"
        sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", fabric_code)
        target_path = self.images_dir / f"{sanitized}{suffix}"

        if target_path.exists():
            return str(target_path)

        try:
            resp = self.session.get(image_url)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  Failed to download image for {fabric_code}: {exc}")
            return None

        target_path.write_bytes(resp.content)
        return str(target_path)

    def save_json(self, records: list[FabricRecord]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / "formens_fabrics.json"

        payload = {
            "source": self.base_url,
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(records),
            "fabrics": [asdict(record) for record in records],
        }

        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print(f"💾 Saved {len(records)} fabrics to {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------
    def run(self) -> Path:
        self.login()
        detail_urls = self.fetch_listing_urls()
        records: list[FabricRecord] = []
        for idx, url in enumerate(detail_urls, 1):
            try:
                records.append(self.scrape_fabric(url))
            except Exception as exc:  # noqa: BLE001
                print(f"❌ Skipping {url}: {exc}")
            if idx % 25 == 0:
                print(f"📊 Progress: {idx}/{len(detail_urls)} fabrics scraped")

        return self.save_json(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Formens B2B fabric data")
    parser.add_argument(
        "--email",
        help="Login email (optional, wenn Benutzername genutzt wird)",
        default=os.getenv("FORMENS_EMAIL"),
    )
    parser.add_argument(
        "--username",
        help="Login-Benutzername (Alternative zum Email-Feld)",
        default=os.getenv("FORMENS_USERNAME"),
    )
    parser.add_argument(
        "--password",
        help="Login password",
        default=os.getenv("FORMENS_PASSWORD"),
    )
    parser.add_argument("--cookie", help="Pre-authenticated session cookie", default=None)
    parser.add_argument("--base-url", help="Portal base URL", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--listing-path",
        help="Path for listing pages (supports {page} placeholder)",
        default=DEFAULT_LISTING_PATH,
    )
    parser.add_argument(
        "--login-path", help="Relative login path", default=DEFAULT_LOGIN_PATH
    )
    parser.add_argument(
        "--max-pages", type=int, default=120, help="Maximum listing pages to scan"
    )
    parser.add_argument(
        "--page-param", default="page", help="Query parameter used for pagination"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("storage/fabrics"),
        help="Directory where JSON and images are stored",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip downloading fabric images",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.7,
        help="Seconds to sleep between requests to avoid throttling",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (only for debugging)",
    )
    parser.add_argument(
        "--allow-anonymous",
        action="store_true",
        help=(
            "Skip authentication if the portal allows anonymous access. "
            "Otherwise the scraper will fail fast when listings redirect to login."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scraper = FormensScraper(
        base_url=args.base_url,
        listing_path=args.listing_path,
        login_path=args.login_path,
        email=args.email,
        username=args.username,
        password=args.password,
        session_cookie=args.cookie,
        output_dir=args.output_dir,
        sleep_seconds=args.sleep,
        max_pages=args.max_pages,
        page_param=args.page_param,
        download_images=not args.no_images,
        verify_tls=not args.insecure,
        allow_anonymous=args.allow_anonymous,
    )
    scraper.run()


if __name__ == "__main__":
    main()
