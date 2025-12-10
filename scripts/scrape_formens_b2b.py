"""Scrape fabric listings from the Formens B2B portal."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class FormensB2BScraper:
    """Handle authentication and listing retrieval for Formens B2B."""

    def __init__(
        self,
        *,
        base_url: str = "https://b2b2.formens.ro",
        login_path: str | None = None,
        email: str | None = None,
        username: str | None = None,
        password: str | None = None,
        session_cookie: str | None = None,
        allow_anonymous: bool = False,
        output_dir: Path | None = None,
        max_pages: int = 1,
    ) -> None:
        self.base_url = base_url
        self.login_path = login_path or "/"
        self.email = email
        self.username = username
        self.password = password
        self.session_cookie = session_cookie
        self.allow_anonymous = allow_anonymous
        self.output_dir = Path(output_dir) if output_dir else None
        self.max_pages = max_pages

        self.session = requests.Session()
        if self.session_cookie:
            self._apply_session_cookie(self.session_cookie)

    def _apply_session_cookie(self, cookie: str) -> None:
        """Apply a provided session cookie to the requests session."""

        if "=" in cookie:
            name, value = cookie.split("=", 1)
            self.session.cookies.set(name.strip(), value.strip())
        else:
            # Fallback to a generic session cookie name
            self.session.cookies.set("PHPSESSID", cookie.strip())

    def login(self) -> None:
        """Perform a form-based login against the Formens portal."""

        if self.session_cookie:
            print("ℹ️  Using provided session cookie (skipping form login).")
            return

        if (not self.email and not self.username) or not self.password:
            if self.allow_anonymous:
                print("⚠️  No credentials provided — continuing without login.")
                return
            raise RuntimeError(
                "Login ist erforderlich — nutze --username/--password oder --email/--password."
            )

        login_page_url = "https://b2b2.formens.ro/"
        print(f"🔐 Fetching login page at {login_page_url} ...")
        resp_get = self.session.get(login_page_url)
        resp_get.raise_for_status()

        soup = BeautifulSoup(resp_get.text, "html.parser")
        form = soup.find("form")
        if not form:
            raise RuntimeError("Konnte auf der Login-Seite kein <form> finden.")

        action = form.get("action") or ""
        action_url = urljoin(login_page_url, action)

        payload: dict[str, str] = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue
            value = inp.get("value") or ""
            payload[name] = value

        login_identifier = self.username or self.email
        if "username" in payload:
            payload["username"] = login_identifier
            identifier_label = "username"
        elif "email" in payload:
            payload["email"] = login_identifier
            identifier_label = "email"
        else:
            payload["username"] = login_identifier
            identifier_label = "username"

        payload["password"] = self.password

        print(
            f"🔐 Logging in at {action_url} with {identifier_label} {login_identifier!r} ..."
        )
        resp_post = self.session.post(action_url, data=payload, allow_redirects=True)
        if resp_post.status_code >= 400:
            raise RuntimeError(
                f"Login failed with status {resp_post.status_code}: {resp_post.text[:200]}"
            )

        if 'name="username"' in resp_post.text and 'name="password"' in resp_post.text:
            raise RuntimeError(
                "Login failed — Login-Formular wird weiterhin angezeigt. Prüfe Credentials."
            )

        print("✅ Login successful (session cookies stored).")

    def fetch_listing_urls(self) -> list[str]:
        """Fetch listing pages and return the visited URLs."""

        listing_urls: list[str] = []
        for page in range(1, self.max_pages + 1):
            url = f"{self.base_url.rstrip('/')}/stocktisue?page={page}"
            print(f"🌐 Listing page {page}: {url}")
            resp = self.session.get(url)
            resp.raise_for_status()

            if 'name="username"' in resp.text and 'name="password"' in resp.text:
                raise RuntimeError(
                    "Received a login page instead of listings. Check login() or session cookies."
                )

            listing_urls.append(url)
            self._maybe_save_listing(page, resp.text)

        return listing_urls

    def _maybe_save_listing(self, page: int, html: str) -> None:
        """Persist listing HTML if an output directory is provided."""

        if not self.output_dir:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"listing_page_{page}.html"
        target.write_text(html, encoding="utf-8")
        print(f"💾 Saved listing page {page} to {target}")

    def run(self) -> list[str]:
        """Execute login and fetch listings."""

        self.login()
        return self.fetch_listing_urls()


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape fabric listings from the Formens B2B portal."
    )
    parser.add_argument("--email", type=str, help="Login email", default=None)
    parser.add_argument("--username", type=str, help="Login username", default=None)
    parser.add_argument("--password", type=str, help="Login password", default=None)
    parser.add_argument(
        "--cookie", type=str, help="Existing session cookie (PHPSESSID=...)", default=None
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional directory to store listing HTML pages.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Number of listing pages to fetch (starting from page=1).",
    )
    parser.add_argument(
        "--allow-anonymous",
        action="store_true",
        help="Proceed without login when no credentials are provided.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])

    scraper = FormensB2BScraper(
        base_url="https://b2b2.formens.ro",
        login_path="/",  # retained for compatibility
        email=args.email,
        username=args.username,
        password=args.password,
        session_cookie=args.cookie,
        allow_anonymous=args.allow_anonymous,
        output_dir=args.output_dir,
        max_pages=args.max_pages,
    )

    try:
        urls = scraper.run()
    except Exception as exc:  # noqa: BLE001 - CLI utility should surface errors plainly
        print(f"❌ Error: {exc}")
        sys.exit(1)

    if urls:
        print("\n✅ Fetched listing pages:")
        for url in urls:
            print(f" - {url}")
    else:
        print("⚠️  No listing pages fetched.")


if __name__ == "__main__":
    main()
