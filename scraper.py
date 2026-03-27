"""
scraper.py — Idealz.lk Competitor Price Scraper  (v4)
=======================================================
Changes in v4:
  - LuxuryX:    Brand new custom engine. Their site is NOT WooCommerce.
                Category pages show LKR 0 (JS rendered). We visit each
                product detail page, wait for JS, then click every
                Storage button + every Color button to get all variant prices.
  - Life Mobile: New variant engine — visits each product page, clicks
                every variation option (RAM/storage/colour) to capture
                all prices. Fixes the "only 8 products" issue.
  - All others: Unchanged from v3.
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

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

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
        "engine": "woocommerce_variants",   # visits detail pages + clicks variants
        "categories": [
            "https://lifemobile.lk/product-category/mobile-phones/",
            "https://lifemobile.lk/product-category/tablets/",
            "https://lifemobile.lk/product-category/accessories/",
            "https://lifemobile.lk/product-category/smart-watches/",
            "https://lifemobile.lk/product-category/earbuds/",
            "https://lifemobile.lk/product-category/laptops/",
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
        "engine": "luxuryx",               # fully custom engine
        # These pages list products with their detail page URLs
        "category_pages": [
            "https://luxuryx.lk/iphone-price-in-sri-lanka",
            "https://luxuryx.lk/macbook-price-in-sri-lanka",
            "https://luxuryx.lk/ipad-price-in-sri-lanka",
            "https://luxuryx.lk/android-price",
            "https://luxuryx.lk/buy-apple-watch-in-sri-lanka",
            "https://luxuryx.lk/airpod-price-in-sri-lanka",
            "https://luxuryx.lk/buy-jbl-speakers-in-sri-lanka",
            "https://luxuryx.lk/laptop-price-in-sri-lanka",
            "https://luxuryx.lk/playstation-price-in-sri-lanka",
            "https://luxuryx.lk/gadgets",
            "https://luxuryx.lk/buy-apple-accessories-online",
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


# ── HELPERS ───────────────────────────────────────────────────────────────────

def clean_price(text):
    """Extract a valid LKR price from any string."""
    if not text:
        return None
    text = str(text).replace(",", "").replace("\u0dbb\u0dd4", "").replace("\u00a0", "").replace(" ", "")
    text = re.sub(r"(Rs\.?|LKR|\u20a8)", "", text, flags=re.IGNORECASE)
    matches = re.findall(r"\d{4,7}(?:\.\d{1,2})?", text)
    if matches:
        val = float(matches[0])
        if 1000 <= val <= 2000000:
            return int(val)
    return None


def clean_variant(text):
    """Normalise variant label. e.g. '256 GB / Black' → '256GB / Black'"""
    if not text:
        return ""
    text = text.strip()
    # Normalise spacing around GB/TB
    text = re.sub(r"(\d+)\s*(GB|TB)", lambda m: f"{m.group(1)}{m.group(2).upper()}", text, flags=re.IGNORECASE)
    # Clean extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:60]


def make_record(name, variant, price, url, site_name):
    return {
        "name":       name.strip(),
        "variant":    clean_variant(variant),
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


def new_context_args():
    return dict(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )


async def block_media(page):
    """Block images, fonts, analytics to speed up scraping."""
    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}", lambda r: r.abort())
    await page.route("**/google-analytics.com/**", lambda r: r.abort())
    await page.route("**/facebook.com/**",         lambda r: r.abort())
    await page.route("**/hotjar.com/**",           lambda r: r.abort())
    await page.route("**/googletagmanager.com/**",  lambda r: r.abort())


# ── ENGINE 1: SHOPIFY JSON API (ONEi) ────────────────────────────────────────

def scrape_shopify_api(base_url, collections, site_name):
    """
    Calls Shopify /products.json API.
    Each variant (storage, RAM, colour) becomes its own row.
    """
    all_rows  = []
    seen_keys = set()
    headers   = {
        "User-Agent": "Mozilla/5.0 (compatible; PriceBot/4.0)",
        "Accept":     "application/json",
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
                    name        = p.get("title", "").strip()
                    product_url = f"{base_url}/products/{p.get('handle', '')}"
                    if not name:
                        continue

                    for v in p.get("variants", []):
                        # Build variant label from option values
                        opts = [
                            str(v.get(f"option{i}", "") or "").strip()
                            for i in range(1, 4)
                        ]
                        opts = [o for o in opts if o and o.lower() not in ("default title", "default", "")]
                        variant = clean_variant(" / ".join(opts))

                        try:
                            price = int(float(v.get("price", 0)))
                        except (ValueError, TypeError):
                            continue
                        if not (1000 <= price <= 2000000):
                            continue

                        key = f"{name.lower()}|{variant.lower()}"
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        all_rows.append(make_record(name, variant, price, product_url, site_name))
                        count += 1

                log(f"  [ONEi API] {handle} p{page}: +{count}", "OK")
                if len(products_raw) < 250:
                    break
                page += 1

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    log(f"  [ONEi API] 404 skipped: {handle}", "WARN")
                else:
                    log(f"  [ONEi API] HTTP {e.code}: {handle}", "WARN")
                break
            except Exception as e:
                log(f"  [ONEi API] Error {handle}: {e}", "ERROR")
                break

    log(f"  ✓ ONEi: {len(all_rows)} variant rows", "OK")
    return all_rows


# ── ENGINE 2: LUXURYX CUSTOM ENGINE ──────────────────────────────────────────

async def scrape_luxuryx(browser, site_config):
    """
    LuxuryX is a fully custom Laravel/Vue site — NOT WooCommerce.
    Category listing pages show LKR 0 because prices load via JS.

    Strategy:
    1. Visit each category page → extract product detail page URLs from the <li> list
       (the price list at the bottom of each category page IS rendered in HTML)
    2. Visit each product detail page
    3. Wait for JS to load the price
    4. Click each Storage button one by one → record price + storage label
    5. For each storage, click each Color button → record colour label
    6. Produces rows: {name, variant="256GB / Cosmic Orange", price}
    """
    site_name    = site_config["name"]
    category_pgs = site_config["category_pages"]

    context = await browser.new_context(**new_context_args())
    page    = await context.new_page()
    await block_media(page)

    # ── Step 1: Collect all product URLs from category pages ──────────────────
    product_links = {}   # url → name

    for cat_url in category_pgs:
        log(f"  [LuxuryX] Category: {cat_url}")
        try:
            await page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)   # JS needs time on this site

            # The category page renders a price list as <ul><li><a href="...">Name LKR X</a></li>
            links = await page.evaluate("""
                () => {
                    const results = [];
                    // Find all anchor tags that link to product detail pages
                    // LuxuryX product URLs follow pattern /product-slug or /category/slug
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href;
                        const text = a.innerText.trim();
                        // Filter: must be same domain, must have product-like text
                        if (
                            href.includes('luxuryx.lk') &&
                            !href.includes('/product-category') &&
                            !href.includes('/shop') &&
                            !href.includes('/brand') &&
                            !href.includes('#') &&
                            text.length > 3 &&
                            text.length < 120 &&
                            !text.toLowerCase().includes('home') &&
                            !text.toLowerCase().includes('menu') &&
                            !text.toLowerCase().includes('cart') &&
                            !text.toLowerCase().includes('wishlist')
                        ) {
                            // Extract name: strip price from text e.g. "iPhone 17 Pro Max LKR 475,000"
                            const name = text.replace(/LKR[\s\d,\.]+/gi, '').trim();
                            if (name.length > 3) {
                                results.push({ href, name });
                            }
                        }
                    });
                    return results;
                }
            """)

            for item in links:
                href = item.get("href", "").split("?")[0]
                name = item.get("name", "").strip()
                # Skip navigation, footer, accessory links that aren't products
                skip_patterns = [
                    "/about", "/contact", "/privacy", "/shipping", "/return",
                    "/brand/", "/res/", "/storage/", "wa.me", "tel:", "mailto:",
                    "facebook.com", "instagram.com", "youtube.com",
                    "iphone-price-in-sri-lanka", "macbook-price-in-sri-lanka",
                    "ipad-price-in-sri-lanka", "android-price", "buy-apple-watch",
                    "airpod-price", "buy-jbl-speakers", "laptop-price",
                    "playstation-price", "/gadgets", "buy-apple-accessories",
                    "brand-new-cars", "products/category",
                ]
                if any(p in href for p in skip_patterns):
                    continue
                if href and name and href not in product_links:
                    product_links[href] = name

            log(f"  [LuxuryX] {cat_url} → {len(links)} links found", "OK")

        except Exception as e:
            log(f"  [LuxuryX] Error on category {cat_url}: {e}", "ERROR")

    log(f"  [LuxuryX] {len(product_links)} unique product pages to visit")

    # ── Step 2: Visit each product page and extract storage + colour variants ──
    all_rows  = []
    seen_keys = set()

    for product_url, product_name in product_links.items():
        try:
            log(f"  [LuxuryX] Product: {product_name[:50]}")
            await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)   # wait for Vue/React to hydrate prices

            # ── Read storage options ──────────────────────────────────────────
            # LuxuryX renders storage as buttons with class like "storage-btn" or
            # inside a div labelled "Storage". We try multiple selectors.
            storage_options = await page.evaluate("""
                () => {
                    // Try to find storage selection buttons
                    const storageSelectors = [
                        '[class*="storage"] button',
                        '[class*="Storage"] button',
                        'button[class*="storage"]',
                        '.storage-options button',
                        '.variant-options button',
                        '[data-storage]',
                        'button[data-option]',
                    ];
                    for (const sel of storageSelectors) {
                        const btns = document.querySelectorAll(sel);
                        if (btns.length > 0) {
                            return [...btns].map(b => ({
                                text:  b.innerText.trim(),
                                index: [...b.parentElement.children].indexOf(b),
                            }));
                        }
                    }

                    // Fallback: find a label "Storage" and get sibling buttons
                    const labels = [...document.querySelectorAll('label, span, p, h3, h4')];
                    for (const lbl of labels) {
                        if (lbl.innerText.trim().toLowerCase() === 'storage') {
                            const parent = lbl.closest('div') || lbl.parentElement;
                            if (parent) {
                                const btns = parent.querySelectorAll('button, [role="button"], li');
                                if (btns.length > 0) {
                                    return [...btns].map(b => ({ text: b.innerText.trim(), index: 0 }));
                                }
                            }
                        }
                    }
                    return [];
                }
            """)

            # ── Read colour options ───────────────────────────────────────────
            color_options = await page.evaluate("""
                () => {
                    const colorSelectors = [
                        '[class*="color"] button',
                        '[class*="Color"] button',
                        'button[class*="color"]',
                        '.color-options button',
                        '[data-color]',
                    ];
                    for (const sel of colorSelectors) {
                        const btns = document.querySelectorAll(sel);
                        if (btns.length > 0) {
                            return [...btns].map(b => b.innerText.trim() || b.getAttribute('title') || b.getAttribute('data-color') || '').filter(t => t.length > 0);
                        }
                    }
                    // Fallback: find label "Color" and look for siblings
                    const labels = [...document.querySelectorAll('label, span, p, h3, h4')];
                    for (const lbl of labels) {
                        if (/^colou?r$/i.test(lbl.innerText.trim())) {
                            const parent = lbl.closest('div') || lbl.parentElement;
                            if (parent) {
                                const btns = parent.querySelectorAll('button, [role="button"], li, span[title]');
                                if (btns.length > 0) {
                                    return [...btns].map(b => b.innerText.trim() || b.getAttribute('title') || '').filter(t => t.length > 0);
                                }
                            }
                        }
                    }
                    return [];
                }
            """)

            # ── Get base price (no variant selected) ─────────────────────────
            async def read_current_price():
                """Read the currently displayed price from the page."""
                return await page.evaluate("""
                    () => {
                        // LuxuryX shows price in multiple possible elements
                        const selectors = [
                            '[class*="price"]:not([class*="original"]):not([class*="old"])',
                            '.product-price',
                            '.current-price',
                            'span[class*="Price"]',
                            'h2[class*="price"]',
                            'p[class*="price"]',
                        ];
                        for (const sel of selectors) {
                            const els = document.querySelectorAll(sel);
                            for (const el of els) {
                                const txt = el.innerText.trim();
                                if (txt && (txt.includes('LKR') || /\d{6}/.test(txt))) {
                                    return txt;
                                }
                            }
                        }
                        // Broad fallback: scan all text for a 6-digit LKR price
                        const all = document.body.innerText;
                        const m = all.match(/LKR\s*([\d,]+)/);
                        return m ? m[0] : '';
                    }
                """)

            if storage_options:
                # Click each storage button, then each colour button
                storage_btns = await page.query_selector_all(
                    '[class*="storage"] button, [class*="Storage"] button, '
                    'button[class*="storage"], .storage-options button, .variant-options button'
                )

                for s_idx, s_opt in enumerate(storage_options):
                    storage_label = s_opt.get("text", "").strip()
                    if not storage_label:
                        continue

                    # Click this storage button
                    if s_idx < len(storage_btns):
                        try:
                            await storage_btns[s_idx].click()
                            await page.wait_for_timeout(800)
                        except Exception:
                            pass

                    if color_options:
                        color_btns = await page.query_selector_all(
                            '[class*="color"] button, [class*="Color"] button, '
                            'button[class*="color"], .color-options button'
                        )
                        for c_idx, color_label in enumerate(color_options):
                            if not color_label:
                                continue
                            if c_idx < len(color_btns):
                                try:
                                    await color_btns[c_idx].click()
                                    await page.wait_for_timeout(600)
                                except Exception:
                                    pass

                            price_text = await read_current_price()
                            price = clean_price(price_text)
                            if price:
                                variant = f"{storage_label} / {color_label}"
                                key = f"{product_name.lower()}|{variant.lower()}"
                                if key not in seen_keys:
                                    seen_keys.add(key)
                                    all_rows.append(make_record(product_name, variant, price, product_url, site_name))
                    else:
                        # No colours — just record storage + price
                        price_text = await read_current_price()
                        price = clean_price(price_text)
                        if price:
                            key = f"{product_name.lower()}|{storage_label.lower()}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                all_rows.append(make_record(product_name, storage_label, price, product_url, site_name))
            else:
                # No storage options found — single price product
                price_text = await read_current_price()
                price = clean_price(price_text)
                if price:
                    # Try to get colour at least
                    colour_label = color_options[0] if color_options else ""
                    key = f"{product_name.lower()}|{colour_label.lower()}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_rows.append(make_record(product_name, colour_label, price, product_url, site_name))

            log(f"  [LuxuryX] {product_name[:40]}: {len([r for r in all_rows if r['name']==product_name.strip()])} variants", "OK")
            await page.wait_for_timeout(500)

        except Exception as e:
            log(f"  [LuxuryX] Error on {product_url}: {e}", "ERROR")

    await context.close()
    log(f"  ✓ LuxuryX: {len(all_rows)} variant rows", "OK")
    return all_rows


# ── ENGINE 3: WOOCOMMERCE STANDARD (listing → WC variation JSON) ──────────────

async def get_wc_listing_stubs(page, url, site_name, extra_wait_ms=0):
    """Scrape WooCommerce category listing page. Returns list of {name, url, base_price}."""
    stubs    = []
    page_num = 1

    while True:
        current_url = url if page_num == 1 else f"{url}page/{page_num}/"
        log(f"  WC listing [{site_name}] p{page_num}: {current_url}")
        try:
            await page.goto(current_url, wait_until="domcontentloaded", timeout=35000)
            try:
                await page.wait_for_selector(
                    "ul.products, .products, li.product, .wc-block-grid__product, .product.type-product",
                    timeout=15000
                )
            except PWTimeout:
                log(f"  [{site_name}] No products on {current_url}", "WARN")
                break
            if extra_wait_ms:
                await page.wait_for_timeout(extra_wait_ms)
        except Exception as e:
            log(f"  [{site_name}] Load failed {current_url}: {e}", "WARN")
            break

        cards = await page.evaluate("""
            () => {
                const results = [];
                const selectors = ['li.product.type-product','li.product','.wc-block-grid__product','[class*="product-card"]','.product.type-product'];
                let cards = [];
                for (const s of selectors) { const f = document.querySelectorAll(s); if (f.length) { cards = f; break; } }
                cards.forEach(c => {
                    const nameEl  = c.querySelector('h2.woocommerce-loop-product__title,h3.woocommerce-loop-product__title,.woocommerce-loop-product__title,.wc-block-grid__product-title,h2,h3');
                    const linkEl  = c.querySelector('a.woocommerce-loop-product__link,a[href*="/product/"],a');
                    const salePEl = c.querySelector('ins .woocommerce-Price-amount,ins bdi');
                    const regPEl  = c.querySelector('.woocommerce-Price-amount bdi,.price bdi,.price .amount,.woocommerce-Price-amount');
                    const priceEl = salePEl || regPEl;
                    if (nameEl && linkEl) results.push({ name: nameEl.innerText.trim(), url: linkEl.href, base_price: priceEl ? priceEl.innerText.trim() : '' });
                });
                return results;
            }
        """)

        for c in cards:
            if c.get("name") and c.get("url"):
                stubs.append(c)

        has_next = await page.query_selector("a.next.page-numbers,.woocommerce-pagination .next,a[rel='next']")
        if not has_next or page_num >= 25:
            break
        page_num += 1
        await page.wait_for_timeout(800)

    return stubs


async def get_wc_variants(page, stub, site_name):
    """
    Visit a WooCommerce product detail page.
    Reads data-product_variations attribute for all variant prices.
    Falls back to clicking dropdowns if the JSON isn't present.
    """
    name = stub["name"]
    url  = stub["url"]
    rows = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
    except Exception as e:
        log(f"  [{site_name}] Cannot open {url}: {e}", "WARN")
        price = clean_price(stub.get("base_price", ""))
        if price:
            rows.append(make_record(name, "", price, url, site_name))
        return rows

    # ── Read WooCommerce variation JSON ───────────────────────────────────────
    var_data = await page.evaluate("""
        () => {
            // Method 1: data-product_variations on the form
            const form = document.querySelector('form.variations_form');
            if (form) {
                const raw = form.getAttribute('data-product_variations');
                if (raw && raw !== 'false') {
                    try { return JSON.parse(raw); } catch(e) {}
                }
            }
            // Method 2: inline script tag
            for (const s of document.querySelectorAll('script:not([src])')) {
                const match = s.textContent.match(/"variations"\s*:\s*(\[[\s\S]*?\])\s*[,}]/);
                if (match) { try { return JSON.parse(match[1]); } catch(e) {} }
            }
            return null;
        }
    """)

    if var_data and isinstance(var_data, list) and len(var_data) > 0:
        seen_v = {}
        for v in var_data:
            price_raw = v.get("display_price") or v.get("price") or ""
            price     = clean_price(str(price_raw))
            if not price:
                continue

            attrs = v.get("attributes", {})
            parts = []
            for attr_key, attr_val in attrs.items():
                if not attr_val:
                    continue
                val_up = attr_val.upper()
                # Include storage/RAM values (contain GB/TB or are numeric+unit)
                if re.search(r"\d+(GB|TB)", val_up) or any(kw in attr_key.lower() for kw in ("storage","memory","ram","capacity","gb","tb","size")):
                    parts.append(attr_val)
                # Include colour values
                elif any(kw in attr_key.lower() for kw in ("color","colour","finish")):
                    parts.append(attr_val)
                else:
                    # Include if it looks like storage or colour
                    if re.search(r"\d+(GB|TB)", val_up):
                        parts.append(attr_val)
                    elif len(attr_val) < 30:
                        parts.append(attr_val)

            variant = clean_variant(" / ".join(parts)) if parts else ""
            k = variant.lower()
            if k not in seen_v or price < seen_v[k]["price"]:
                seen_v[k] = make_record(name, variant, price, url, site_name)

        rows = list(seen_v.values())

    else:
        # ── Fallback: click each select option ────────────────────────────────
        selects = await page.query_selector_all("form.variations_form select, .variations select")
        if selects:
            # Get all option combinations
            all_options = []
            for sel in selects:
                options = await sel.evaluate("""
                    el => [...el.options]
                        .filter(o => o.value && o.value !== '')
                        .map(o => ({ value: o.value, text: o.text.trim() }))
                """)
                all_options.append(options)

            # Try each option in the first select (storage/RAM)
            for opt in all_options[0] if all_options else []:
                try:
                    await selects[0].select_option(opt["value"])
                    await page.wait_for_timeout(800)

                    price_raw = await page.evaluate("""
                        () => {
                            const el = document.querySelector('.woocommerce-variation-price .woocommerce-Price-amount bdi, .single-price, .price .woocommerce-Price-amount');
                            return el ? el.innerText : '';
                        }
                    """)
                    price = clean_price(price_raw)
                    if price:
                        variant = clean_variant(opt["text"])
                        rows.append(make_record(name, variant, price, url, site_name))
                except Exception:
                    pass
        else:
            # Simple (non-variable) product
            price_raw = await page.evaluate("""
                () => {
                    const el = document.querySelector('.woocommerce-Price-amount bdi,.price bdi,.price .amount,.summary .price');
                    return el ? el.innerText : '';
                }
            """)
            price = clean_price(price_raw) or clean_price(stub.get("base_price", ""))
            if price:
                rows.append(make_record(name, "", price, url, site_name))

    return rows


# ── ENGINE 4: WOOCOMMERCE WITH VARIANTS (Life Mobile + others) ───────────────

async def scrape_woocommerce_variants(browser, site_config):
    """
    Full WooCommerce scrape:
    Phase 1 — listing pages → collect product URLs
    Phase 2 — visit each product page → extract all variants
    """
    name       = site_config["name"]
    categories = site_config.get("categories", [])
    extra_wait = site_config.get("wait_extra_ms", 0)

    context      = await browser.new_context(**new_context_args())
    listing_page = await context.new_page()
    detail_page  = await context.new_page()
    await block_media(listing_page)
    await block_media(detail_page)

    # Phase 1: collect stubs
    all_stubs = []
    seen_urls = set()
    for cat_url in categories:
        try:
            stubs = await get_wc_listing_stubs(listing_page, cat_url, name, extra_wait)
            for s in stubs:
                if s["url"] not in seen_urls:
                    seen_urls.add(s["url"])
                    all_stubs.append(s)
            await listing_page.wait_for_timeout(700)
        except Exception as e:
            log(f"  [{name}] Listing error {cat_url}: {e}", "ERROR")

    log(f"  [{name}] {len(all_stubs)} products to visit")

    # Phase 2: visit each product and get variants
    all_rows     = []
    seen_records = set()
    for i, stub in enumerate(all_stubs, 1):
        try:
            rows = await get_wc_variants(detail_page, stub, name)
            for r in rows:
                key = f"{r['name'].lower()}|{r['variant'].lower()}"
                if key not in seen_records:
                    seen_records.add(key)
                    all_rows.append(r)
            if i % 10 == 0:
                await detail_page.wait_for_timeout(500)
        except Exception as e:
            log(f"  [{name}] Detail error: {e}", "ERROR")

    await context.close()
    log(f"  ✓ {name}: {len(all_rows)} variant rows", "OK")
    return all_rows


# ── ENGINE 5: WOOCOMMERCE STANDARD (listing + WC variation JSON, no detail pages) ──

async def scrape_woocommerce_standard(browser, site_config):
    """
    For sites like Celltronics, Present Solution, Genius Mobile.
    Uses WooCommerce variation JSON from detail pages.
    """
    return await scrape_woocommerce_variants(browser, site_config)


# ── SITE ORCHESTRATOR ─────────────────────────────────────────────────────────

async def scrape_site(browser, site_key, site_config):
    name   = site_config["name"]
    engine = site_config["engine"]
    log(f"\n{'━'*58}\n  SCRAPING: {name.upper()}  [{engine}]\n{'━'*58}")

    if engine == "shopify_api":
        return scrape_shopify_api(
            site_config["base"], site_config["collections"], name
        )
    elif engine == "luxuryx":
        return await scrape_luxuryx(browser, site_config)
    elif engine in ("woocommerce", "woocommerce_variants"):
        return await scrape_woocommerce_variants(browser, site_config)
    else:
        log(f"  Unknown engine: {engine}", "ERROR")
        return []


# ── MAIN RUNNER ───────────────────────────────────────────────────────────────

async def run_scraper(target_sites=None, headless=True):
    today = datetime.now().strftime("%Y-%m-%d")
    sites = {k: v for k, v in SITES.items() if not target_sites or k in target_sites}
    log(f"\n{'═'*58}\n  IDEALZ SCRAPER v4 — {today}\n  Sites: {', '.join(sites.keys())}\n{'═'*58}")

    all_results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
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

    log(f"\n{'═'*58}\n  COMPLETE — {len(all_results)} total rows\n{'═'*58}")
    for site, count in sorted(by_site.items(), key=lambda x: -x[1]):
        flag = "" if count > 5 else "  ← CHECK THIS SITE"
        log(f"  {site:<25} {count:>5} rows{flag}")
    log(f"\n  → {json_path}\n  → {csv_path}\n")
    return all_results, json_path, csv_path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Idealz.lk Price Scraper v4 — with variants")
    parser.add_argument("--site", nargs="+", choices=list(SITES.keys()))
    parser.add_argument("--headless", type=lambda x: x.lower() != "false", default=True)
    args = parser.parse_args()
    asyncio.run(run_scraper(args.site, args.headless))
