"""
scraper.py — Idealz.lk Competitor Price Scraper  (v3 — with variants)
=======================================================================
What's new in v3:
  - Every product VARIANT is captured as a separate row
    e.g. iPhone 17 Pro Max 256GB, iPhone 17 Pro Max 512GB, iPhone 17 Pro Max 1TB
  - ONEi:         Shopify /products.json API (all variants per product)
  - Celltronics:  Visits each product detail page to extract all variants
  - LuxuryX:      Correct URLs + visits detail pages for variants
  - Genius Mobile: All 17 categories + variant extraction
  - Present Solution: Variant extraction from detail pages
  - Life Mobile:  Variant extraction from detail pages

Output columns:  name, variant, price, site, url, scraped_at
  e.g. name="iPhone 17 Pro Max"  variant="256GB"  price=459900

Usage:
  python scraper.py                        # all sites
  python scraper.py --site onei            # one site
  python scraper.py --site celltronics
  python scraper.py --headless false       # watch browser (debug)
"""

import asyncio
import json
import csv
import re
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ── SITE DEFINITIONS ──────────────────────────────────────────────────────────

SITES = {
    "celltronics": {
        "name": "Celltronics",
        "base": "https://celltronics.lk",
        "engine": "woocommerce",
        "categories": [
            "https://celltronics.lk/product-category/mobile-phones/apple/",
            "https://celltronics.lk/product-category/mobile-phones/samsung/",
            "https://celltronics.lk/product-category/mobile-phones/google/",
            "https://celltronics.lk/product-category/mobile-phones/oneplus/",
            "https://celltronics.lk/product-category/mobile-phones/xiaomi/",
            "https://celltronics.lk/product-category/mobile-phones/oppo/",
            "https://celltronics.lk/product-category/mobile-phones/realme/",
            "https://celltronics.lk/product-category/mobile-phones/infinix/",
            "https://celltronics.lk/product-category/ipads-and-tablets/apple-ipads/",
            "https://celltronics.lk/product-category/ipads-and-tablets/samsung-tablets/",
            "https://celltronics.lk/product-category/macbook-price-in-sri-lanka/",
            "https://celltronics.lk/product-category/smart-watches-and-fitness-bands/smart-watches/",
            "https://celltronics.lk/product-category/bluetooth-earbuds/",
            "https://celltronics.lk/product-category/headphones/",
            "https://celltronics.lk/product-category/bluetooth-speakers/",
        ],
    },
    "lifemobile": {
        "name": "Life Mobile",
        "base": "https://lifemobile.lk",
        "engine": "woocommerce",
        "categories": [
            "https://lifemobile.lk/product-category/mobile-phones/",
            "https://lifemobile.lk/product-category/tablets/",
            "https://lifemobile.lk/product-category/accessories/",
        ],
    },
    "onei": {
        "name": "ONEi",
        "base": "https://onei.lk",
        "engine": "shopify_api",
        "collections": [
            "new-iphones", "samsung-phones", "google-pixel", "redmi",
            "honor", "oneplus", "tecno", "vivo", "nothing", "infinix",
            "blackview", "macbook-air", "macbook-pro", "macbook-neo",
            "imac", "new-ipads", "ipad-air", "ipad-pro", "apple-watch",
            "airpods", "apple-accessories", "sony", "jbl", "marshall",
            "anker", "baseus", "powerology", "dji", "insta360",
            "ps5", "console", "meta-quest", "dyson", "pre-owned-iphones-1",
        ],
    },
    "luxuryx": {
        "name": "LuxuryX",
        "base": "https://luxuryx.lk",
        "engine": "woocommerce",
        "wait_extra_ms": 3000,
        "categories": [
            "https://luxuryx.lk/shop/",
            "https://luxuryx.lk/product-category/smartphones/",
            "https://luxuryx.lk/product-category/mobile-phones/",
            "https://luxuryx.lk/product-category/apple/",
            "https://luxuryx.lk/product-category/samsung/",
            "https://luxuryx.lk/product-category/tablets/",
            "https://luxuryx.lk/product-category/ipads/",
            "https://luxuryx.lk/product-category/laptops/",
            "https://luxuryx.lk/product-category/macbooks/",
            "https://luxuryx.lk/product-category/accessories/",
            "https://luxuryx.lk/product-category/smartwatches/",
            "https://luxuryx.lk/product-category/earbuds/",
        ],
    },
    "presentsolution": {
        "name": "Present Solution",
        "base": "https://presentsolution.lk",
        "engine": "woocommerce",
        "categories": [
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-17-series/",
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-16-series/",
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-15-series/",
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-14-series/",
            "https://presentsolution.lk/product-category/best-mobile-phones-sri-lanka/android-phones-sri-lanka/samsung/",
            "https://presentsolution.lk/product-category/best-mobile-phones-sri-lanka/android-phones-sri-lanka/google-pixel/",
            "https://presentsolution.lk/product-category/best-mobile-phones-sri-lanka/android-phones-sri-lanka/redmi/",
            "https://presentsolution.lk/product-category/mac-sri-lanka/macbook-air/",
            "https://presentsolution.lk/product-category/mac-sri-lanka/macbook-pro/",
            "https://presentsolution.lk/product-category/mac-sri-lanka/mac-mini/",
            "https://presentsolution.lk/product-category/mac-sri-lanka/imac/",
            "https://presentsolution.lk/product-category/ipad/",
            "https://presentsolution.lk/product-category/watches/apple-watch/",
            "https://presentsolution.lk/product-category/watches/galaxy-watch/",
            "https://presentsolution.lk/product-category/earbuds-sri-lanka/airpods/",
            "https://presentsolution.lk/product-category/earbuds-sri-lanka/galaxy-buds/",
            "https://presentsolution.lk/product-category/earbuds-sri-lanka/soundcore/",
        ],
    },
    "geniusmobile": {
        "name": "Genius Mobile",
        "base": "https://www.geniusmobile.lk",
        "engine": "woocommerce",
        "categories": [
            "https://www.geniusmobile.lk/shop/",
            "https://www.geniusmobile.lk/product-category/mobile-phones/",
            "https://www.geniusmobile.lk/product-category/apple/",
            "https://www.geniusmobile.lk/product-category/iphone/",
            "https://www.geniusmobile.lk/product-category/samsung/",
            "https://www.geniusmobile.lk/product-category/xiaomi/",
            "https://www.geniusmobile.lk/product-category/redmi/",
            "https://www.geniusmobile.lk/product-category/oppo/",
            "https://www.geniusmobile.lk/product-category/realme/",
            "https://www.geniusmobile.lk/product-category/vivo/",
            "https://www.geniusmobile.lk/product-category/infinix/",
            "https://www.geniusmobile.lk/product-category/tecno/",
            "https://www.geniusmobile.lk/product-category/nokia/",
            "https://www.geniusmobile.lk/product-category/tablets/",
            "https://www.geniusmobile.lk/product-category/accessories/",
            "https://www.geniusmobile.lk/product-category/earbuds/",
            "https://www.geniusmobile.lk/product-category/smartwatches/",
        ],
    },
}

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


# ── HELPERS ───────────────────────────────────────────────────────────────────

def clean_price(text):
    """Extract a valid LKR price from any string."""
    if not text:
        return None
    text = str(text).replace(",", "").replace("\u0dbb\u0dd4", "").replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"(Rs\.?|\u20a8|LKR)", "", text, flags=re.IGNORECASE)
    matches = re.findall(r"\d{4,7}(?:\.\d{1,2})?", text)
    if matches:
        val = float(matches[0])
        if 1000 <= val <= 2000000:
            return int(val)
    return None


def clean_variant(text):
    """
    Normalise a variant label.
    '256 GB / Black' → '256GB'
    '16GB RAM + 512GB' → '16GB / 512GB'
    'Titanium Black 256' → '256GB'
    Returns '' if nothing meaningful found.
    """
    if not text:
        return ""
    text = text.strip()

    # Extract storage sizes (128GB, 256GB, 512GB, 1TB, 2TB)
    storage = re.findall(r"\b(\d+)\s*(GB|TB)\b", text, re.IGNORECASE)
    # Extract RAM sizes (4GB, 6GB, 8GB, 12GB, 16GB, 24GB, 32GB)
    ram = re.findall(r"\b([4-9]|1[0-9]|2[0-9]|3[0-2])\s*GB\b", text, re.IGNORECASE)

    parts = []
    # Add RAM if clearly RAM-sized (≤32GB)
    for r in ram:
        if int(r) <= 32:
            parts.append(f"{r}GB RAM")
    # Add storage (>= 32GB treated as storage)
    for size, unit in storage:
        if unit.upper() == "TB" or int(size) > 32:
            parts.append(f"{size}{unit.upper()}")

    if parts:
        return " / ".join(parts)

    # Fallback: return cleaned original text (truncated)
    cleaned = re.sub(r"[^a-zA-Z0-9 /\-]", "", text).strip()
    return cleaned[:40] if cleaned else ""


def make_record(name, variant, price, url, site_name):
    return {
        "name":       name,
        "variant":    variant,
        "price":      price,
        "site":       site_name,
        "url":        url,
        "scraped_at": datetime.now().isoformat(),
    }


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "●", "OK": "✓", "WARN": "⚠", "ERROR": "✗"}
    line = f"[{ts}] {symbols.get(level, '·')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_DIR / "scraper.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── SHOPIFY JSON API — ONEi (all variants) ────────────────────────────────────

def scrape_shopify_api(base_url, collections, site_name):
    """
    Calls Shopify's /products.json API.
    Each variant (256GB, 512GB, 1TB, different RAM configs) becomes its own row.
    """
    all_rows = []
    seen_keys = set()  # "product_name|variant" dedup key

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PriceBot/3.0)",
        "Accept": "application/json",
    }

    for handle in collections:
        log(f"  [ONEi API] {handle}")
        page = 1
        while True:
            url = f"{base_url}/collections/{handle}/products.json?limit=250&page={page}"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                products_raw = data.get("products", [])
                if not products_raw:
                    break

                count = 0
                for p in products_raw:
                    name = p.get("title", "").strip()
                    if not name:
                        continue

                    product_url = f"{base_url}/products/{p.get('handle', '')}"
                    variants    = p.get("variants", [])

                    for v in variants:
                        # Build variant label from Shopify option values
                        option_vals = [
                            str(v.get(f"option{i}", "") or "").strip()
                            for i in range(1, 4)
                        ]
                        # Filter out generic / "Default" values
                        option_vals = [
                            o for o in option_vals
                            if o and o.lower() not in ("default title", "default", "")
                        ]
                        variant_raw = " / ".join(option_vals)
                        variant     = clean_variant(variant_raw) or variant_raw[:40]

                        try:
                            price = int(float(v.get("price", 0)))
                        except (ValueError, TypeError):
                            continue

                        if not (1000 <= price <= 2000000):
                            continue

                        dedup_key = f"{name.lower()}|{variant.lower()}"
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)

                        all_rows.append(make_record(name, variant, price, product_url, site_name))
                        count += 1

                log(f"  [ONEi API] {handle} p{page}: +{count} rows", "OK")
                if len(products_raw) < 250:
                    break
                page += 1

            except urllib.error.HTTPError as e:
                code = e.code
                if code == 404:
                    log(f"  [ONEi API] 404 skipped: {handle}", "WARN")
                else:
                    log(f"  [ONEi API] HTTP {code}: {handle}", "WARN")
                break
            except Exception as e:
                log(f"  [ONEi API] Error {handle}: {e}", "ERROR")
                break

    log(f"  ✓ ONEi: {len(all_rows)} variant rows total", "OK")
    return all_rows


# ── WOOCOMMERCE — LISTING PAGE (collects product URLs) ───────────────────────

async def get_product_urls_from_listing(page, url, site_name, extra_wait_ms=0):
    """
    Scrapes a WooCommerce category listing page.
    Returns list of {name, url, base_price} dicts — one per product card.
    Handles pagination.
    """
    product_stubs = []
    page_num = 1

    while True:
        current_url = url if page_num == 1 else f"{url}page/{page_num}/"
        log(f"  WC listing [{site_name}] p{page_num}: {current_url}")

        try:
            await page.goto(current_url, wait_until="domcontentloaded", timeout=35000)
            try:
                await page.wait_for_selector(
                    "ul.products, .products, li.product, .wc-block-grid__product, "
                    "[class*='product-card'], .product.type-product",
                    timeout=15000
                )
            except PWTimeout:
                log(f"  [{site_name}] No product grid on {current_url}", "WARN")
                break

            if extra_wait_ms > 0:
                await page.wait_for_timeout(extra_wait_ms)

        except Exception as e:
            log(f"  [{site_name}] Failed loading {current_url}: {e}", "WARN")
            break

        cards = await page.evaluate("""
            () => {
                const results = [];
                const selectors = [
                    'li.product.type-product', 'li.product',
                    '.wc-block-grid__product', '[class*="product-card"]',
                    '.product-item', '.product.type-product',
                ];
                let cards = [];
                for (const s of selectors) {
                    const f = document.querySelectorAll(s);
                    if (f.length > 0) { cards = f; break; }
                }

                cards.forEach(card => {
                    const nameEl = card.querySelector(
                        'h2.woocommerce-loop-product__title, h3.woocommerce-loop-product__title, ' +
                        '.woocommerce-loop-product__title, .wc-block-grid__product-title, ' +
                        'h2.product-title, h3.product-title, .product-title, h2, h3'
                    );
                    const linkEl = card.querySelector(
                        'a.woocommerce-loop-product__link, a[href*="/product/"], a'
                    );
                    // Grab the displayed (possibly sale) price as fallback
                    const salePEl  = card.querySelector('ins .woocommerce-Price-amount, ins bdi');
                    const regPEl   = card.querySelector('.woocommerce-Price-amount bdi, .price bdi, .price .amount, .woocommerce-Price-amount');
                    const priceEl  = salePEl || regPEl;

                    if (nameEl && linkEl) {
                        results.push({
                            name:       nameEl.innerText.trim(),
                            url:        linkEl.href,
                            base_price: priceEl ? priceEl.innerText.trim() : '',
                        });
                    }
                });
                return results;
            }
        """)

        for c in cards:
            if c.get("name") and c.get("url"):
                product_stubs.append(c)

        log(f"  [{site_name}] Listing p{page_num}: {len(cards)} products found", "OK")

        has_next = await page.query_selector(
            "a.next.page-numbers, .woocommerce-pagination .next, a[rel='next']"
        )
        if not has_next or page_num >= 25:
            break
        page_num += 1
        await page.wait_for_timeout(1000)

    return product_stubs


# ── WOOCOMMERCE — PRODUCT DETAIL PAGE (extracts all variants) ────────────────

async def get_variants_from_product_page(page, stub, site_name):
    """
    Opens a WooCommerce product detail page and extracts ALL variant combinations.

    Strategy:
    1. Check if the page has a variable product (dropdowns / swatches).
    2. If yes: read the variation JSON embedded in the page (wc_product_variations)
       which WooCommerce always injects as a JS object — very reliable.
    3. If no variations: return single row with base price.
    """
    name      = stub["name"]
    url       = stub["url"]
    rows      = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
    except Exception as e:
        log(f"  [{site_name}] Cannot open {url}: {e}", "WARN")
        # Fall back to base price from listing
        price = clean_price(stub.get("base_price", ""))
        if price:
            rows.append(make_record(name, "", price, url, site_name))
        return rows

    # ── Try to read WooCommerce variation data from page JS ───────────────────
    variation_data = await page.evaluate("""
        () => {
            // WooCommerce injects product variations into a global JS object.
            // Try multiple known variable names across different themes.
            const sources = [
                window.wc_add_to_cart_variation_params,
                window.woodmart_settings,
            ];

            // Also search <script> tags for the JSON
            for (const script of document.querySelectorAll('script:not([src])')) {
                const txt = script.textContent || '';

                // Look for the variations array WooCommerce always injects
                const match = txt.match(/"variations"\s*:\s*(\[[\s\S]*?\])\s*[,}]/);
                if (match) {
                    try { return { type: 'inline', variations: JSON.parse(match[1]) }; }
                    catch(e) {}
                }

                // WC also serialises it as form_data attribute
                const formMatch = txt.match(/variations_form.*?"variations"\s*:\s*(\[[\s\S]+?\])/);
                if (formMatch) {
                    try { return { type: 'form', variations: JSON.parse(formMatch[1]) }; }
                    catch(e) {}
                }
            }

            // Read from the data attribute on the variations form element
            const form = document.querySelector('form.variations_form');
            if (form) {
                const raw = form.getAttribute('data-product_variations');
                if (raw && raw !== 'false') {
                    try { return { type: 'form_attr', variations: JSON.parse(raw) }; }
                    catch(e) {}
                }
            }

            // No variations found
            return null;
        }
    """)

    if variation_data and variation_data.get("variations"):
        variations = variation_data["variations"]
        log(f"  [{site_name}] {name}: {len(variations)} variants found via JS", "OK")

        for v in variations:
            # Price: prefer sale price if available
            price_raw = (
                v.get("display_price")
                or v.get("price")
                or ""
            )
            price = clean_price(str(price_raw))
            if not price:
                continue

            # Build variant label from attributes
            attrs = v.get("attributes", {})
            # attrs looks like: {"attribute_pa_storage": "256gb", "attribute_pa_color": "black"}
            variant_parts = []
            for attr_key, attr_val in attrs.items():
                if not attr_val:
                    continue
                # Only include storage/RAM attributes, skip colour
                key_lower = attr_key.lower()
                val_lower = attr_val.lower()
                if any(kw in key_lower for kw in ("storage", "memory", "ram", "capacity", "gb", "tb", "size")):
                    variant_parts.append(attr_val.upper())
                elif re.search(r"\d+(gb|tb)", val_lower):
                    variant_parts.append(attr_val.upper())

            variant = clean_variant(" / ".join(variant_parts)) if variant_parts else ""

            # If still empty, build from variation description
            if not variant:
                desc = v.get("variation_description", "") or ""
                variant = clean_variant(desc)

            rows.append(make_record(name, variant, price, url, site_name))

        # Deduplicate: same name+variant, keep lowest price
        seen_v = {}
        for r in rows:
            k = r["variant"].lower()
            if k not in seen_v or r["price"] < seen_v[k]["price"]:
                seen_v[k] = r
        rows = list(seen_v.values())

    else:
        # Simple product — no variants, just grab the price from the page
        price_raw = await page.evaluate("""
            () => {
                const el = document.querySelector(
                    '.woocommerce-Price-amount bdi, ' +
                    '.price .woocommerce-Price-amount, ' +
                    '.price bdi, ' +
                    '.summary .price'
                );
                return el ? el.innerText : '';
            }
        """)
        price = clean_price(price_raw) or clean_price(stub.get("base_price", ""))
        if price:
            rows.append(make_record(name, "", price, url, site_name))

    return rows


# ── WOOCOMMERCE FULL SCRAPE (listing → detail pages) ─────────────────────────

async def scrape_woocommerce_site(browser, site_config):
    name         = site_config["name"]
    extra_wait   = site_config.get("wait_extra_ms", 0)
    categories   = site_config.get("categories", [])

    # One context for listing pages, one for detail pages
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    listing_page = await context.new_page()
    detail_page  = await context.new_page()

    # Block images, fonts, analytics for speed
    for p in [listing_page, detail_page]:
        await p.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}", lambda r: r.abort())
        await p.route("**/google-analytics.com/**", lambda r: r.abort())
        await p.route("**/facebook.com/**",         lambda r: r.abort())
        await p.route("**/hotjar.com/**",           lambda r: r.abort())

    # ── Phase 1: collect all product stubs from listing pages ─────────────────
    all_stubs   = []
    seen_urls   = set()
    for cat_url in categories:
        try:
            stubs = await get_product_urls_from_listing(listing_page, cat_url, name, extra_wait)
            for s in stubs:
                if s["url"] not in seen_urls:
                    seen_urls.add(s["url"])
                    all_stubs.append(s)
            await listing_page.wait_for_timeout(800)
        except Exception as e:
            log(f"  [{name}] Listing error {cat_url}: {e}", "ERROR")

    log(f"  [{name}] {len(all_stubs)} unique products to visit for variants")

    # ── Phase 2: visit each product page and extract variants ─────────────────
    all_rows     = []
    seen_records = set()  # "name|variant" dedup

    for i, stub in enumerate(all_stubs, 1):
        try:
            rows = await get_variants_from_product_page(detail_page, stub, name)
            for r in rows:
                key = f"{r['name'].lower()}|{r['variant'].lower()}"
                if key not in seen_records:
                    seen_records.add(key)
                    all_rows.append(r)
            # Brief pause every 10 products to be polite
            if i % 10 == 0:
                await detail_page.wait_for_timeout(500)
        except Exception as e:
            log(f"  [{name}] Detail error {stub.get('url','')}: {e}", "ERROR")

    await context.close()
    log(f"  ✓ {name}: {len(all_rows)} variant rows", "OK")
    return all_rows


# ── SITE ORCHESTRATOR ─────────────────────────────────────────────────────────

async def scrape_site(browser, site_key, site_config):
    name   = site_config["name"]
    engine = site_config["engine"]
    log(f"\n{'━'*58}\n  SCRAPING: {name.upper()}  [{engine}]\n{'━'*58}")

    if engine == "shopify_api":
        return scrape_shopify_api(
            site_config["base"],
            site_config["collections"],
            name,
        )

    return await scrape_woocommerce_site(browser, site_config)


# ── MAIN RUNNER ───────────────────────────────────────────────────────────────

async def run_scraper(target_sites=None, headless=True):
    today = datetime.now().strftime("%Y-%m-%d")
    sites = {k: v for k, v in SITES.items() if not target_sites or k in target_sites}
    log(f"\n{'═'*58}\n  IDEALZ SCRAPER v3 (variants) — {today}\n  Sites: {len(sites)}\n{'═'*58}")

    all_results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        for site_key, site_config in sites.items():
            try:
                rows = await scrape_site(browser, site_key, site_config)
                all_results.extend(rows)
            except Exception as e:
                log(f"FATAL on {site_key}: {e}", "ERROR")

        await browser.close()

    # ── Save outputs ──────────────────────────────────────────────────────────
    json_path = OUTPUT_DIR / f"prices_{today}.json"
    csv_path  = OUTPUT_DIR / f"prices_{today}.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    fieldnames = ["name", "variant", "price", "site", "url", "scraped_at"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    # ── Summary ───────────────────────────────────────────────────────────────
    from collections import defaultdict
    by_site = defaultdict(int)
    for r in all_results:
        by_site[r["site"]] += 1

    log(f"\n{'═'*58}\n  SCRAPE COMPLETE — {len(all_results)} variant rows total\n{'═'*58}")
    for site, count in sorted(by_site.items(), key=lambda x: -x[1]):
        flag = "" if count > 5 else "  ← CHECK THIS SITE"
        log(f"  {site:<25} {count:>5} rows{flag}")
    log(f"\n  → {json_path}\n  → {csv_path}\n")

    return all_results, json_path, csv_path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Idealz.lk Price Scraper v3 — with variants")
    parser.add_argument(
        "--site", nargs="+",
        choices=list(SITES.keys()),
        help="Scrape specific site(s) only. Default: all."
    )
    parser.add_argument(
        "--headless",
        type=lambda x: x.lower() != "false",
        default=True,
        help="Headless browser mode. Use --headless false to watch."
    )
    args = parser.parse_args()
    asyncio.run(run_scraper(args.site, args.headless))
