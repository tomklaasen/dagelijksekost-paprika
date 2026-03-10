#!/usr/bin/env python3
"""Import today's Dagelijkse Kost recipe into Paprika."""

import argparse
import gzip
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from recipe_scrapers import scrape_html

DAGELIJKSEKOST_URL = "https://dagelijksekost.vrt.be"
PAPRIKA_API = "https://www.paprikaapp.com/api"

log = logging.getLogger(__name__)


def get_todays_recipe_url() -> str:
    """Find today's recipe URL from the Dagelijkse Kost homepage."""
    resp = requests.get(f"{DAGELIJKSEKOST_URL}/", timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the element containing "Vandaag" text, then find the ancestor <a>
    vandaag = soup.find(string=lambda t: t and "Vandaag" in t)
    if not vandaag:
        raise ValueError("Could not find 'Vandaag in Dagelijkse kost' on the homepage.")

    anchor = vandaag.find_parent("a")
    if not anchor or not anchor.get("href"):
        raise ValueError("Could not find recipe link near 'Vandaag' text.")

    return DAGELIJKSEKOST_URL + anchor["href"]


def get_paprika_token(email: str, password: str) -> str:
    """Authenticate with Paprika and return a bearer token."""
    resp = requests.post(
        f"{PAPRIKA_API}/v1/account/login/",
        data={"email": email, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["result"]["token"]


def format_minutes(minutes: int) -> str:
    """Convert minutes to a human-readable string."""
    if minutes <= 0:
        return ""
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"


def compute_hash(recipe: dict) -> str:
    """Compute the SHA256 hash of the recipe, excluding the hash field itself."""
    fields = {k: v for k, v in recipe.items() if k != "hash"}
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True).encode("utf-8")
    ).hexdigest()


def fetch_photo(image_url: str | None) -> tuple[dict, bytes | None]:
    """Download an image and return photo fields for the recipe JSON plus raw bytes.

    Paprika expects:
    - recipe['photo'] = '<uuid>.jpg'  (a filename, not base64)
    - recipe['photo_hash'] = SHA256 of the raw image bytes
    - The raw image bytes sent as 'photo_upload' in the same multipart request
    """
    if not image_url:
        return {"photo": None, "photo_hash": None, "photo_large": None}, None
    try:
        resp = requests.get(image_url, timeout=10)
        resp.raise_for_status()
        data = resp.content
        filename = f"{uuid.uuid4()}.jpg"
        photo_hash = hashlib.sha256(data).hexdigest()
        return {"photo": filename, "photo_hash": photo_hash, "photo_large": None}, data
    except Exception as e:
        log.warning("Failed to fetch photo from %s: %s", image_url, e)
        return {"photo": None, "photo_hash": None, "photo_large": None}, None


def scrape_recipe(url: str) -> tuple[dict, bytes | None]:
    """Fetch and parse a recipe page, returning a Paprika recipe dict and photo bytes."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    scraper = scrape_html(html, org_url=url)

    # og:title has the clean name; the schema 'name' field is a teaser sentence
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        name = og_title["content"]
    else:
        h1 = soup.find("h1")
        name = h1.get_text(strip=True) if h1 else ""

    def safe(fn, default=None):
        try:
            result = fn()
            return result if result is not None else default
        except Exception:
            return default

    photo_fields, photo_bytes = fetch_photo(safe(scraper.image, None))

    recipe = {
        "uid": str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
        "name": name,
        "ingredients": "\n".join(safe(scraper.ingredients, [])),
        "directions": safe(scraper.instructions, ""),
        "description": safe(scraper.description, ""),
        "notes": "",
        "source": "Dagelijkse Kost",
        "source_url": url,
        "prep_time": format_minutes(safe(scraper.prep_time, 0)),
        "cook_time": format_minutes(safe(scraper.cook_time, 0)),
        "total_time": format_minutes(safe(scraper.total_time, 0)),
        "servings": safe(scraper.yields, ""),
        "difficulty": "",
        "rating": 0,
        "image_url": safe(scraper.image, None),
        **photo_fields,
        "photo_url": None,
        "scale": None,
        "nutritional_info": "",
        "categories": [],
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "in_trash": False,
        "is_pinned": False,
        "on_favorites": False,
        "on_grocery_list": False,
        "hash": "",
    }
    recipe["hash"] = compute_hash(recipe)
    return recipe, photo_bytes


def upload_recipe(recipe: dict, photo_bytes: bytes | None, token: str) -> None:
    """Upload a recipe (and optional photo) to Paprika."""
    compressed = gzip.compress(json.dumps(recipe).encode("utf-8"))
    files = {"data": compressed}
    if photo_bytes:
        files["photo_upload"] = (recipe["photo"], photo_bytes, "image/jpeg")

    resp = requests.post(
        f"{PAPRIKA_API}/v2/sync/recipe/{recipe['uid']}/",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("result"):
        raise RuntimeError(f"Paprika upload failed: {result}")


def main():
    parser = argparse.ArgumentParser(description="Import today's Dagelijkse Kost recipe into Paprika.")
    parser.add_argument("--dry-run", action="store_true", help="Scrape and print the recipe without uploading to Paprika.")
    args = parser.parse_args()

    load_dotenv()

    if not args.dry_run:
        email = os.environ.get("PAPRIKA_EMAIL")
        password = os.environ.get("PAPRIKA_PASSWORD")
        if not email or not password:
            print("Error: set PAPRIKA_EMAIL and PAPRIKA_PASSWORD in .env or environment.")
            sys.exit(1)

    print("Finding today's recipe...")
    recipe_url = get_todays_recipe_url()
    print(f"  {recipe_url}")

    print("Scraping recipe...")
    recipe, photo_bytes = scrape_recipe(recipe_url)

    if args.dry_run:
        dry_run_output = {**recipe, "photo": f"<{len(photo_bytes)} bytes>" if photo_bytes else None}
        print(json.dumps(dry_run_output, indent=2, ensure_ascii=False))
        return

    print(f"  {recipe['name']}")

    print("Authenticating with Paprika...")
    token = get_paprika_token(email, password)

    print("Uploading to Paprika...")
    upload_recipe(recipe, photo_bytes, token)

    print("Done!")


if __name__ == "__main__":
    main()
