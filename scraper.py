"""
scraper.py — Idealz.lk Competitor Price Scraper
=================================================
Scrapes all 6 competitor websites and saves:
  data/prices_YYYY-MM-DD.json
  data/prices_YYYY-MM-DD.csv

Usage:
  python scraper.py                        # all sites
  python scraper.py --site celltronics     # one site
  python scraper.py --headless false       # watch browser
"""

import asyncio
import json
import csv
import re
import os
import argparse
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

SITES = {
    "celltronics": {
        "name": "Celltronics",
        "base": "https://celltronics.lk",
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
        "engine": "woocommerce",
    },
    "lifemobile": {
        "name": "Life Mobile",
        "base": "https://lifemobile.lk",
        "categories": [
            "https://lifemobile.lk/product-category/mobile-phones/",
            "https://lifemobile.lk/product-category/tablets/",
            "https://lifemobile.lk/product-category/accessories/",
        ],
        "engine": "woocommerce",
    },
    "onei": {
        "name": "ONEi",
        "base": "https://onei.lk",
        "categories": [
            "https://onei.lk/collections/new-iphones",
            "https://onei.lk/collections/samsung-phones",
            "https://onei.lk/collections/google-pixel",
            "https://onei.lk/collections/redmi",
            "https://onei.lk/collections/honor",
            "https://onei.lk/collections/oneplus",
            "https://onei.lk/collections/tecno",
            "https://onei.lk/collections/vivo",
            "https://onei.lk/collections/nothing",
            "https://onei.lk/collections/infinix",
            "https://onei.lk/collections/macbook-air",
            "https://onei.lk/collections/macbook-pro",
            "https://onei.lk/collections/new-ipads",
            "https://onei.lk/collections/apple-watch",
            "https://onei.lk/collections/airpods",
            "https://onei.lk/collections/sony",
            "https://onei.lk/collections/jbl",
            "https://onei.lk/collections/anker",
            "https://onei.lk/collections/dji",
        ],
        "engine": "shopify",
    },
    "luxuryx": {
        "name": "LuxuryX",
        "base": "https://luxuryx.lk",
        "categories": [
            "https://luxuryx.lk/product-category/mobile-phones/",
            "https://luxuryx.lk/product-category/tablets/",
            "https://luxuryx.lk/product-category/laptops/",
            "https://luxuryx.lk/product-category/accessories/",
        ],
        "engine": "woocommerce",
    },
    "presentsolution": {
        "name": "Present Solution",
        "base": "https://presentsolution.lk",
        "categories": [
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-17-series/",
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-16-series/",
            "https://presentsolution.lk/product-category/mobile-phones/iphone/iphone-15-series/",
            "https://presentsolution.lk/product-category/best-mobile-phones-sri-lanka/android-phones-sri-lanka/samsung/",
            "https://presentsolution.lk/product-category/best-mobile-phones-sri-lanka/android-phones-sri-lanka/google-pixel/",
            "https://presentsolution.lk/product-category/mac-sri-lanka/macbook-air/",
            "https://presentsolution.lk/product-category/mac-sri-lanka/macbook-pro/",
            "https://presentsolution.lk/product-category/ipad/",
            "https://presentsolution.lk/product-category/watches/apple-watch/",
            "https://presentsolution.lk/product-category/watches/galaxy-watch/",
            "https://presentsolution.lk/product-category/earbuds-sri-lanka/airpods/",
            "https://presentsolution.lk/product-category/earbuds-sri-lanka/galaxy-buds/",
        ],
        "engine": "woocommerce",
    },
    "geniusmobile": {
        "name": "Genius Mobile",
        "base": "https://www.geniusmobile.lk",
        "categories": [
            "https://www.geniusmobile.lk/product-category/mobile-phones/",
            "https://www.geniusmobile.lk/product-category/samsung/",
            "https://www.geniusmobile.lk/product-category/xiaomi/",
            "https://www.geniusmobile.lk/product-category/oppo/",
            "https://www.geniusmobile.lk/product-category/realme/",
            "https://www.geniusmobile.lk/product-category/infinix/",
        ],
        "engine": "woocommerce",
    },
}

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def clean_price(text):
    if not text:
        return None
    text = text.replace(",", "").replace("\u0dbb\u0dd4", "").replace(" ", "")
    text = re.sub(r"(Rs\.?|\u20a8)", "", text, flags=re.IGNORECASE)
    matches = re.findall(r"\d{4,7}(?:\.\d{1,2})?", text)
    if matches:
        val = float(matches[0])
        if 1000 <= val <= 2000000:
            return int(val)
    return None


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "●", "OK": "✓", "WARN": "⚠", "ERROR": "✗"}
    line = f"[{ts}] {symbols.get(level,'·')} {msg}"
    print(line)
    with open(LOG_DIR / "scraper.log", "a") as f:
        f.write(line + "\n")


async def scrape_woocommerce(page, url, site_name):
    products = []
    page_num = 1
    while True:
        current_url = url if page_num == 1 else f"{url}page/{page_num}/"
        log(f"  WooCommerce [{site_name}] p{page_num}: {current_url}")
        try:
            await page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(
                ".products, ul.products, .woocommerce-loop-product, .product-grid",
                timeout=12000
            )
        except Exception as e:
            log(f"  [{site_name}] No products / timeout on page {page_num}: {e}", "WARN")
            break

        items = await page.evaluate("""
            () => {
                const results = [];
                const selectors = ['li.product','div.product-item','.woocommerce-loop-product','.product.type-product'];
                let cards = [];
                for (const s of selectors) { cards = document.querySelectorAll(s); if (cards.length) break; }
                cards.forEach(card => {
                    const nameEl = card.querySelector('h2.woocommerce-loop-product__title,h3.product-title,h2,h3');
                    const salePriceEl = card.querySelector('ins .woocommerce-Price-amount,ins bdi');
                    const regularPriceEl = card.querySelector('.woocommerce-Price-amount,.price bdi,.price .amount');
                    const priceEl = salePriceEl || regularPriceEl;
                    const linkEl = card.querySelector('a.woocommerce-loop-product__link,a');
                    if (nameEl && priceEl) results.push({
                        name: nameEl.innerText.trim(),
                        price_text: priceEl.innerText.trim(),
                        url: linkEl ? linkEl.href : ''
                    });
                });
                return results;
            }
        """)
        for item in items:
            price = clean_price(item.get("price_text", ""))
            if item.get("name") and price:
                products.append({
                    "name": item["name"], "price": price,
                    "url": item.get("url", ""), "site": site_name,
                    "scraped_at": datetime.now().isoformat()
                })
        has_next = await page.query_selector("a.next.page-numbers,.woocommerce-pagination .next,a[rel='next']")
        if not has_next or page_num >= 20:
            break
        page_num += 1
        await page.wait_for_timeout(800)
    return products


async def scrape_shopify(page, url, site_name):
    products = []
    log(f"  Shopify [{site_name}]: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector(".product-item,.card-wrapper,[data-product-id],.grid__item", timeout=12000)
    except Exception as e:
        log(f"  [{site_name}] Error: {e}", "WARN")
        return products

    for _ in range(30):
        lb = await page.query_selector("button[name='load-more'],.load-more,button.btn--load-more")
        if lb:
            await lb.click()
            await page.wait_for_timeout(1500)
        else:
            break
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1500)

    items = await page.evaluate("""
        () => {
            const results = [];
            const selectors = ['.product-item','.card-wrapper','.grid__item','[data-product-id]'];
            let cards = [];
            for (const s of selectors) { cards = document.querySelectorAll(s); if (cards.length > 3) break; }
            cards.forEach(card => {
                const nameEl = card.querySelector('.card__heading a,.product-item__title,h3 a,h2 a,.product-title');
                const priceEl = card.querySelector('.price__regular .price-item,.price-item--regular,.price__sale .price-item,.price');
                const linkEl = card.querySelector('a[href*="/products/"]');
                if (nameEl && priceEl) results.push({
                    name: nameEl.innerText.trim(),
                    price_text: priceEl.innerText.trim(),
                    url: linkEl ? linkEl.href : ''
                });
            });
            return results;
        }
    """)
    for item in items:
        price = clean_price(item.get("price_text", ""))
        if item.get("name") and price:
            products.append({
                "name": item["name"], "price": price,
                "url": item.get("url", ""), "site": site_name,
                "scraped_at": datetime.now().isoformat()
            })
    log(f"  [{site_name}] {len(products)} products", "OK")
    return products


async def scrape_site(browser, site_key, site_config):
    log(f"\n{'━'*55}\n  SCRAPING: {site_config['name'].upper()}\n{'━'*55}")
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
    )
    page = await context.new_page()
    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda r: r.abort())
    await page.route("**/google-analytics.com/**", lambda r: r.abort())

    all_products = []
    seen = set()
    for cat_url in site_config["categories"]:
        try:
            if site_config["engine"] == "shopify":
                prods = await scrape_shopify(page, cat_url, site_config["name"])
            else:
                prods = await scrape_woocommerce(page, cat_url, site_config["name"])
            for p in prods:
                key = p["name"].lower().strip()
                if key not in seen:
                    seen.add(key)
                    all_products.append(p)
            await page.wait_for_timeout(1000)
        except Exception as e:
            log(f"  Failed on {cat_url}: {e}", "ERROR")

    await context.close()
    log(f"  ✓ {site_config['name']}: {len(all_products)} unique products", "OK")
    return all_products


async def run_scraper(target_sites=None, headless=True):
    today = datetime.now().strftime("%Y-%m-%d")
    sites_to_scrape = {k: v for k, v in SITES.items() if not target_sites or k in target_sites}
    log(f"\n{'═'*55}\n  IDEALZ SCRAPER — {today}  ({len(sites_to_scrape)} sites)\n{'═'*55}")

    all_results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        for site_key, site_config in sites_to_scrape.items():
            try:
                products = await scrape_site(browser, site_key, site_config)
                all_results.extend(products)
            except Exception as e:
                log(f"FATAL on {site_key}: {e}", "ERROR")
        await browser.close()

    json_path = OUTPUT_DIR / f"prices_{today}.json"
    csv_path  = OUTPUT_DIR / f"prices_{today}.csv"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name","price","site","url","scraped_at"])
        writer.writeheader()
        writer.writerows(all_results)

    from collections import defaultdict
    by_site = defaultdict(int)
    for p in all_results:
        by_site[p["site"]] += 1
    log(f"\n{'═'*55}\n  DONE: {len(all_results)} products\n{'═'*55}")
    for site, count in sorted(by_site.items(), key=lambda x: -x[1]):
        log(f"  {site:<25} {count:>4}")
    log(f"\n  → {json_path}\n  → {csv_path}\n")
    return all_results, json_path, csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", nargs="+", choices=list(SITES.keys()))
    parser.add_argument("--headless", type=lambda x: x.lower() != "false", default=True)
    args = parser.parse_args()
    asyncio.run(run_scraper(args.site, args.headless))
