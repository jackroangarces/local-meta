from __future__ import annotations

import re
import json
import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

RANKINGS_URL = "https://www.schustats.com/regional_rankings"   
DATA_ROOT = Path("data/raw/rankings")

def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown-region"

def fetch_rankings_page() -> str:
    html = asyncio.run(fetch_rendered_html(RANKINGS_URL))
    return html

async def fetch_rendered_html(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        page.on("console", lambda msg: print("CONSOLE:", msg.type, msg.text))
        page.on("pageerror", lambda err: print("PAGE ERROR:", err))
        page.on(
            "response",
            lambda response: (
                print("BAD RESPONSE:", response.status, response.url)
                if response.status >= 400
                else None
            ),
        )

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)

        await page.screenshot(path="debug_page.png", full_page=True)

        html = await page.content()
        await browser.close()
        return html

def save_source_html(html: str, output_dir: Path) -> None:
    (output_dir / "source.html").write_text(html, encoding="utf-8")

# Goes through HTML and extracts region images
# Returns a list of dictionaries with the region name and image URL
def extract_region_images(html: str) -> list[dict[str, str]]:    
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        full_url = urljoin(RANKINGS_URL, src)

        # Extract region name from previous paragraph
        prev_p = img.find_previous("p")
        if not prev_p:
            continue
        text = prev_p.get_text(strip=True)
        if "," in text:
            region = text.split(",", 1)[0]
        else:
            region = text  # fallback

        region = region.strip()

        # Account for SoCal being different
        if region.lower().startswith("socal"):
            region = "SoCal"

        results.append({
            "region": region,
            "image_url": full_url
        })

    # De-duplicate by image URL
    seen: set[str] = set()
    deduped = []

    for item in results:
        if item["image_url"] in seen:
            continue
        seen.add(item["image_url"])
        deduped.append(item)

    return deduped

def download_image(image_url: str, destination: Path) -> None:
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    destination.write_bytes(response.content)


def write_manifest(regions: list[dict[str, str]], output_dir: Path) -> None:
    manifest = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "source_url": RANKINGS_URL,
        "regions": regions,
    }

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    snapshot_name = datetime.now().strftime("%Y-%m-%d")
    output_dir = DATA_ROOT / snapshot_name
    output_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_rankings_page()
    save_source_html(html, output_dir)

    regions = extract_region_images(html)

    enriched_regions: list[dict[str, str]] = []
    used_filenames: set[str] = set()

    for item in regions:
        region = item["region"]
        image_url = item["image_url"]

        base_name = slugify(region)
        filename = f"{base_name}.png"

        # Account for duplicate filenames
        counter = 2
        while filename in used_filenames:
            filename = f"{base_name}-{counter}.png"
            counter += 1

        used_filenames.add(filename)

        local_path = output_dir / filename
        download_image(image_url, local_path)

        enriched_regions.append(
            {
                "region": region,
                "image_url": image_url,
                "local_path": filename,
            }
        )

    write_manifest(enriched_regions, output_dir)

    print(f"Saved {len(enriched_regions)} ranking images to {output_dir}")

# Only run main if the script is executed directly
if __name__ == "__main__":
    main()