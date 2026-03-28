"""
dashboard.py — Idealz.lk Live Price Intelligence Dashboard (v5)
================================================================
Generates a fully self-contained HTML file — no server needed.
The entire scraped dataset is embedded as JSON inside the HTML.
Open in any browser. Works offline.

Features:
  - Product search + filter by Brand / Storage / Shop / Price range
  - Product cards with price comparison across all shops
  - Charts: brand coverage, shop comparison bar chart, price gap heatmap
  - CEO summary: top opportunities, market position
  - Fully responsive, works on mobile

Usage:
  python dashboard.py          # uses latest data file
  python dashboard.py --open   # auto-opens in browser
"""

import json
import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

SITE_ORDER = [
    "Celltronics",
    "ONEi",
    "Present Solution",
    "Life Mobile",
    "LuxuryX",
    "Genius Mobile",
]

SITE_COLORS = {
    "Celltronics":      "#0ea5e9",
    "ONEi":             "#8b5cf6",
    "Present Solution": "#10b981",
    "Life Mobile":      "#f59e0b",
    "LuxuryX":          "#f43f5e",
    "Genius Mobile":    "#ec4899",
}

BRAND_KEYWORDS = {
    "Apple":       ["iphone", "ipad", "macbook", "airpod", "apple watch", "imac", "mac mini", "mac studio", "apple"],
    "Samsung":     ["samsung", "galaxy"],
    "Google":      ["google pixel", "pixel"],
    "Sony":        ["sony"],
    "OnePlus":     ["oneplus"],
    "Xiaomi":      ["xiaomi", "redmi", "poco"],
    "Oppo":        ["oppo"],
    "Realme":      ["realme"],
    "Vivo":        ["vivo"],
    "Infinix":     ["infinix"],
    "Tecno":       ["tecno"],
    "Honor":       ["honor"],
    "Nokia":       ["nokia"],
    "Nothing":     ["nothing", "cmf"],
    "JBL":         ["jbl"],
    "Sony Audio":  ["sony wh", "sony wf", "sony ult"],
    "Anker":       ["anker", "soundcore"],
    "DJI":         ["dji", "osmo", "insta360"],
    "PlayStation": ["playstation", "ps5"],
    "Dyson":       ["dyson"],
    "Other":       [],
}

CATEGORY_KEYWORDS = {
    "Smartphones":  ["iphone", "galaxy", "pixel", "oneplus", "xiaomi", "redmi", "oppo", "realme", "vivo", "infinix", "tecno", "honor", "nokia", "nothing"],
    "MacBooks":     ["macbook"],
    "iPads":        ["ipad"],
    "Tablets":      ["tab ", "tablet"],
    "Smart Watches":["watch", "band"],
    "Earbuds":      ["airpod", "buds", "earbuds", "earbud", "wf-", "soundcore", "cmf buds"],
    "Headphones":   ["headphone", "wh-", "wh1000", "xm5", "xm6"],
    "Speakers":     ["speaker", "jbl", "soundbar"],
    "MacBook":      ["macbook"],
    "Laptops":      ["laptop", "notebook"],
    "Gaming":       ["playstation", "ps5", "xbox", "meta quest"],
    "Cameras":      ["dji", "osmo", "insta360", "gopro"],
    "Accessories":  ["case", "charger", "cable", "adapter", "screen"],
    "Other":        [],
}


def detect_brand(name):
    nl = name.lower()
    for brand, kws in BRAND_KEYWORDS.items():
        if brand == "Other":
            continue
        for kw in kws:
            if kw in nl:
                return brand
    return "Other"


def detect_category(name):
    nl = name.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if cat == "Other":
            continue
        for kw in kws:
            if kw in nl:
                return cat
    return "Other"


def extract_storage(variant):
    """Extract storage label from variant string e.g. '256GB / Black' → '256GB'"""
    if not variant:
        return ""
    m = re.search(r"(\d+\s*(?:GB|TB))", variant, re.IGNORECASE)
    if m:
        s = m.group(1).replace(" ", "")
        return s.upper()
    return ""


def extract_color(variant):
    """Extract colour from variant string."""
    if not variant:
        return ""
    # Remove storage part
    cleaned = re.sub(r"\d+\s*(?:GB|TB)", "", variant, flags=re.IGNORECASE)
    cleaned = cleaned.replace("/", "").strip(" /-")
    return cleaned if len(cleaned) > 1 else ""


def load_latest():
    files = sorted(DATA_DIR.glob("prices_*.json"), reverse=True)
    if not files:
        print("No data files found. Run scraper.py first.")
        sys.exit(1)
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    date_str = files[0].stem.replace("prices_", "")
    return data, date_str


def process(records):
    """
    Build a product map: product_key → {name, brand, category, variants: {storage: {site: price}}}
    """
    products = {}   # key → product dict

    for r in records:
        name    = r.get("name", "").strip()
        variant = r.get("variant", "").strip()
        price   = r.get("price")
        site    = r.get("site", "").strip()
        url     = r.get("url", "")

        if not name or not price or not site:
            continue
        if price < 1000 or price > 5000000:
            continue

        brand    = detect_brand(name)
        category = detect_category(name)
        storage  = extract_storage(variant)
        color    = extract_color(variant)

        # Key = product name (group all variants under same product)
        pkey = name.lower().strip()

        if pkey not in products:
            products[pkey] = {
                "name":     name,
                "brand":    brand,
                "category": category,
                "variants": {},   # storage → {site → {price, url, color}}
                "all_prices": [],
            }

        p = products[pkey]

        # Use storage as variant key; if none, use variant text or "Standard"
        vkey = storage or variant or "Standard"

        if vkey not in p["variants"]:
            p["variants"][vkey] = {}

        existing = p["variants"][vkey].get(site)
        if existing is None or price < existing["price"]:
            p["variants"][vkey][site] = {
                "price": price,
                "url":   url,
                "color": color,
            }

        p["all_prices"].append(price)

    # Compute summary stats per product
    result = []
    for pkey, p in products.items():
        all_p = [
            info["price"]
            for vdata in p["variants"].values()
            for info in vdata.values()
        ]
        if not all_p:
            continue

        # Sites that carry this product
        sites_carrying = set()
        for vdata in p["variants"].values():
            sites_carrying.update(vdata.keys())

        # Market low / high across all variants + sites
        market_low  = min(all_p)
        market_high = max(all_p)

        result.append({
            "name":            p["name"],
            "brand":           p["brand"],
            "category":        p["category"],
            "variants":        p["variants"],
            "storage_options": sorted(p["variants"].keys()),
            "sites":           sorted(sites_carrying),
            "site_count":      len(sites_carrying),
            "market_low":      market_low,
            "market_high":     market_high,
            "spread":          market_high - market_low,
            "spread_pct":      round((market_high - market_low) / market_low * 100, 1) if market_low else 0,
        })

    result.sort(key=lambda x: (-x["site_count"], x["name"].lower()))
    return result


def generate_html(records, date_str):
    products   = process(records)
    fmt_date   = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    total_vars = len(records)

    # Site counts
    site_counts = defaultdict(int)
    for r in records:
        site_counts[r.get("site", "")] += 1

    # Brand counts
    brand_counts = defaultdict(int)
    for p in products:
        brand_counts[p["brand"]] += 1

    # All unique values for filters
    all_brands     = sorted(set(p["brand"]   for p in products))
    all_categories = sorted(set(p["category"] for p in products))
    all_storages   = sorted(set(
        s for p in products for s in p["storage_options"]
        if s and s != "Standard"
    ), key=lambda x: (
        0 if "GB" in x and int(re.search(r"\d+", x).group()) < 100 else
        1 if "GB" in x else 2,
        int(re.search(r"\d+", x).group()) if re.search(r"\d+", x) else 0
    ))

    # Embed data as JSON for the frontend
    js_data = json.dumps(products, ensure_ascii=False)
    js_sites = json.dumps(SITE_ORDER)
    js_site_colors = json.dumps(SITE_COLORS)
    js_site_counts = json.dumps(dict(site_counts))
    js_brand_counts = json.dumps(dict(brand_counts))

    # Build filter pill HTML helpers
    def pills(items, js_fn, extra=""):
        out = f'<button class="pill active" onclick="{js_fn}(\'all\',this)">All</button>'
        for item in items:
            out += f'<button class="pill" onclick="{js_fn}(\'{item.replace("'","")}\',this)">{item}</button>'
        return out

    brand_pills    = pills(all_brands,     "filterBrand")
    cat_pills      = pills(all_categories, "filterCat")
    storage_pills  = pills(all_storages,   "filterStorage")
    shop_pills     = pills(SITE_ORDER,     "filterShop")

    site_count_pills = ""
    for site in SITE_ORDER:
        c = site_counts.get(site, 0)
        col = SITE_COLORS.get(site, "#999")
        site_count_pills += f'''<div class="site-pill" style="border-top-color:{col}">
          <div class="site-pill-name" style="color:{col}">{site}</div>
          <div class="site-pill-count">{c:,}</div>
          <div class="site-pill-label">variants</div>
        </div>'''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idealz.lk — Price Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#07090f;
  --s1:#0d1117;
  --s2:#161b22;
  --s3:#21262d;
  --border:#30363d;
  --accent:#58a6ff;
  --green:#3fb950;
  --red:#f85149;
  --orange:#d29922;
  --purple:#bc8cff;
  --pink:#f778ba;
  --text:#e6edf3;
  --muted:#7d8590;
  --dim:#484f58;
  --font-d:'Syne',sans-serif;
  --font-b:'DM Sans',sans-serif;
  --font-m:'DM Mono',monospace;
  --rad:8px;
  --rad-lg:12px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-b);min-height:100vh;font-size:14px}}

/* ── TOPBAR ── */
.topbar{{
  background:rgba(13,17,23,.95);
  border-bottom:1px solid var(--border);
  padding:14px 28px;
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:200;
  backdrop-filter:blur(12px);
}}
.logo{{font-family:var(--font-d);font-size:18px;font-weight:800;letter-spacing:-0.5px}}
.logo em{{font-style:normal;color:var(--accent)}}
.topbar-right{{display:flex;align-items:center;gap:12px}}
.badge{{font-family:var(--font-m);font-size:10px;padding:3px 10px;border-radius:20px;letter-spacing:.5px}}
.badge-blue{{background:rgba(88,166,255,.1);color:var(--accent);border:1px solid rgba(88,166,255,.25)}}
.badge-green{{background:rgba(63,185,80,.1);color:var(--green);border:1px solid rgba(63,185,80,.25)}}
.topbar-date{{font-family:var(--font-m);font-size:10px;color:var(--muted)}}

/* ── LAYOUT ── */
.layout{{display:grid;grid-template-columns:260px 1fr;min-height:calc(100vh - 53px)}}

/* ── SIDEBAR ── */
.sidebar{{
  background:var(--s1);
  border-right:1px solid var(--border);
  padding:20px 16px;
  position:sticky;
  top:53px;
  height:calc(100vh - 53px);
  overflow-y:auto;
}}
.sidebar::-webkit-scrollbar{{width:4px}}
.sidebar::-webkit-scrollbar-track{{background:transparent}}
.sidebar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}

.filter-section{{margin-bottom:24px}}
.filter-label{{font-family:var(--font-m);font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px;display:block}}

/* Search */
.search-wrap{{position:relative;margin-bottom:20px}}
.search-wrap input{{
  width:100%;background:var(--s2);border:1px solid var(--border);
  border-radius:var(--rad);color:var(--text);font-family:var(--font-b);
  font-size:13px;padding:9px 12px 9px 36px;outline:none;transition:border-color .15s;
}}
.search-wrap input:focus{{border-color:var(--accent)}}
.search-wrap input::placeholder{{color:var(--dim)}}
.search-icon{{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--dim);font-size:14px}}

/* Pills */
.pill-wrap{{display:flex;flex-wrap:wrap;gap:5px}}
.pill{{
  font-size:11px;font-family:var(--font-m);padding:4px 10px;
  border-radius:20px;border:1px solid var(--border);
  background:transparent;color:var(--muted);cursor:pointer;
  transition:all .15s;white-space:nowrap;
}}
.pill:hover{{border-color:var(--accent);color:var(--accent)}}
.pill.active{{background:rgba(88,166,255,.12);border-color:var(--accent);color:var(--accent)}}

/* Price range */
.range-wrap{{display:flex;gap:8px;align-items:center}}
.range-wrap input[type=number]{{
  flex:1;background:var(--s2);border:1px solid var(--border);
  border-radius:var(--rad);color:var(--text);font-family:var(--font-m);
  font-size:12px;padding:7px 10px;outline:none;
}}
.range-wrap input:focus{{border-color:var(--accent)}}
.range-sep{{color:var(--muted);font-size:12px}}

/* Sort */
.sort-select{{
  width:100%;background:var(--s2);border:1px solid var(--border);
  border-radius:var(--rad);color:var(--text);font-family:var(--font-b);
  font-size:13px;padding:8px 10px;outline:none;cursor:pointer;
}}

/* Result count */
.result-count{{font-family:var(--font-m);font-size:11px;color:var(--muted);margin-top:16px;text-align:center}}
.result-count span{{color:var(--accent);font-weight:500}}

/* ── MAIN ── */
.main{{padding:24px 24px;overflow-y:auto}}

/* Stats row */
.stats-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.stat-card{{
  background:var(--s1);border:1px solid var(--border);
  border-radius:var(--rad-lg);padding:16px 18px;
  position:relative;overflow:hidden;
}}
.stat-card::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:var(--accent-color,var(--accent));
}}
.stat-label{{font-family:var(--font-m);font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}}
.stat-val{{font-family:var(--font-d);font-size:28px;font-weight:800;color:var(--accent-color,var(--accent));letter-spacing:-1px;line-height:1}}
.stat-sub{{font-size:11px;color:var(--muted);margin-top:4px}}

/* Site coverage pills */
.site-pills-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}}
.site-pill{{
  background:var(--s1);border:1px solid var(--border);
  border-radius:var(--rad-lg);padding:12px 16px;
  border-top:3px solid;text-align:center;min-width:120px;
}}
.site-pill-name{{font-family:var(--font-m);font-size:10px;font-weight:500;letter-spacing:.5px;text-transform:uppercase;margin-bottom:4px}}
.site-pill-count{{font-family:var(--font-d);font-size:22px;font-weight:800;color:var(--text);line-height:1}}
.site-pill-label{{font-size:10px;color:var(--muted);margin-top:2px}}

/* View toggle */
.view-toggle{{display:flex;gap:4px;margin-bottom:20px}}
.view-btn{{
  font-family:var(--font-m);font-size:11px;padding:6px 14px;
  border:1px solid var(--border);border-radius:var(--rad);
  background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;
}}
.view-btn.active{{background:rgba(88,166,255,.1);border-color:var(--accent);color:var(--accent)}}

/* ── PRODUCT GRID ── */
#product-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
#product-grid.list-view{{grid-template-columns:1fr}}

/* Product card */
.product-card{{
  background:var(--s1);border:1px solid var(--border);
  border-radius:var(--rad-lg);overflow:hidden;
  transition:border-color .2s,transform .2s;
  animation:fadeIn .3s ease;
}}
.product-card:hover{{border-color:rgba(88,166,255,.4);transform:translateY(-2px)}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}

.card-header{{padding:14px 16px 10px;border-bottom:1px solid var(--s3)}}
.card-brand{{font-family:var(--font-m);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}}
.card-name{{font-size:14px;font-weight:600;color:var(--text);line-height:1.3}}
.card-meta{{display:flex;align-items:center;gap:8px;margin-top:6px}}
.cat-badge{{font-family:var(--font-m);font-size:9px;padding:2px 7px;border-radius:20px;background:var(--s3);color:var(--muted);border:1px solid var(--border)}}
.sites-badge{{font-family:var(--font-m);font-size:9px;padding:2px 7px;border-radius:20px;border:1px solid rgba(88,166,255,.3);color:var(--accent);background:rgba(88,166,255,.08)}}

/* Storage selector tabs */
.storage-tabs{{display:flex;gap:4px;padding:10px 16px 0;flex-wrap:wrap}}
.storage-tab{{
  font-family:var(--font-m);font-size:10px;padding:3px 9px;
  border-radius:4px;border:1px solid var(--border);
  background:transparent;color:var(--muted);cursor:pointer;transition:all .12s;
}}
.storage-tab:hover{{border-color:var(--accent);color:var(--accent)}}
.storage-tab.active{{background:rgba(88,166,255,.12);border-color:var(--accent);color:var(--accent)}}

/* Price rows */
.price-rows{{padding:10px 16px 14px}}
.price-row{{
  display:flex;align-items:center;justify-content:space-between;
  padding:6px 0;border-bottom:1px solid var(--s3);
}}
.price-row:last-child{{border-bottom:none}}
.price-site{{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted)}}
.site-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.price-val{{font-family:var(--font-m);font-size:13px;font-weight:500}}
.price-low{{color:var(--green)}}
.price-high{{color:var(--red)}}
.price-mid{{color:var(--text)}}
.price-na{{color:var(--dim);font-size:11px}}
.price-link{{text-decoration:none;color:inherit}}
.price-link:hover .price-val{{text-decoration:underline}}

/* Spread bar */
.spread-bar{{
  margin:8px 16px 0;padding:8px 10px;
  background:var(--s2);border-radius:var(--rad);
  display:flex;align-items:center;justify-content:space-between;
  font-family:var(--font-m);font-size:10px;color:var(--muted);
}}
.spread-val{{color:var(--orange);font-weight:500}}

/* ── TABLE VIEW ── */
.tbl-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:var(--rad-lg)}}
#product-table{{width:100%;border-collapse:collapse;min-width:800px}}
#product-table thead tr{{background:var(--s2)}}
#product-table th{{
  padding:10px 12px;text-align:left;
  font-family:var(--font-m);font-size:9px;color:var(--muted);
  letter-spacing:1.5px;text-transform:uppercase;
  border-bottom:1px solid var(--border);white-space:nowrap;
}}
#product-table th.site-th{{text-align:right;cursor:pointer}}
#product-table th.site-th:hover{{color:var(--text)}}
#product-table tbody tr{{border-bottom:1px solid rgba(48,54,61,.5);transition:background .1s}}
#product-table tbody tr:hover{{background:rgba(88,166,255,.03)}}
#product-table td{{padding:10px 12px;vertical-align:middle;font-size:12px}}
.tbl-name{{font-weight:500;font-size:13px}}
.tbl-variant{{font-family:var(--font-m);font-size:10px;color:var(--muted);margin-top:2px}}
.tbl-brand{{font-family:var(--font-m);font-size:10px;color:var(--muted)}}
.tbl-price{{font-family:var(--font-m);font-size:12px;text-align:right;white-space:nowrap}}

/* ── EMPTY STATE ── */
.empty{{text-align:center;padding:60px 20px;color:var(--muted)}}
.empty-icon{{font-size:40px;margin-bottom:12px}}
.empty-text{{font-size:14px}}

/* ── RESPONSIVE ── */
@media(max-width:900px){{
  .layout{{grid-template-columns:1fr}}
  .sidebar{{position:static;height:auto;border-right:none;border-bottom:1px solid var(--border)}}
  .stats-row{{grid-template-columns:repeat(2,1fr)}}
}}
@media(max-width:600px){{
  .topbar{{padding:12px 14px}}
  .main{{padding:14px}}
  .stats-row{{grid-template-columns:1fr 1fr}}
  #product-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <div class="logo"><em>Idealz</em>.lk — Price Intelligence</div>
  <div class="topbar-right">
    <span class="badge badge-green">LIVE</span>
    <span class="badge badge-blue" id="total-badge">{total_vars:,} VARIANTS</span>
    <span class="topbar-date">{fmt_date.upper()}</span>
  </div>
</div>

<div class="layout">

  <!-- ═══ SIDEBAR ═══ -->
  <aside class="sidebar">

    <!-- Search -->
    <div class="search-wrap">
      <span class="search-icon">⌕</span>
      <input type="text" id="search-input" placeholder="Search product..." oninput="applyFilters()">
    </div>

    <!-- Brand filter -->
    <div class="filter-section">
      <span class="filter-label">Brand</span>
      <div class="pill-wrap" id="brand-pills">{brand_pills}</div>
    </div>

    <!-- Category filter -->
    <div class="filter-section">
      <span class="filter-label">Category</span>
      <div class="pill-wrap" id="cat-pills">{cat_pills}</div>
    </div>

    <!-- Storage filter -->
    <div class="filter-section">
      <span class="filter-label">Storage</span>
      <div class="pill-wrap" id="storage-pills">{storage_pills}</div>
    </div>

    <!-- Shop filter -->
    <div class="filter-section">
      <span class="filter-label">Shop</span>
      <div class="pill-wrap" id="shop-pills">{shop_pills}</div>
    </div>

    <!-- Price range -->
    <div class="filter-section">
      <span class="filter-label">Price Range (LKR)</span>
      <div class="range-wrap">
        <input type="number" id="price-min" placeholder="Min" oninput="applyFilters()" step="10000">
        <span class="range-sep">—</span>
        <input type="number" id="price-max" placeholder="Max" oninput="applyFilters()" step="10000">
      </div>
    </div>

    <!-- Sort -->
    <div class="filter-section">
      <span class="filter-label">Sort By</span>
      <select class="sort-select" id="sort-select" onchange="applyFilters()">
        <option value="shops">Most shops first</option>
        <option value="price-low">Price: Low to High</option>
        <option value="price-high">Price: High to Low</option>
        <option value="spread">Biggest price gap</option>
        <option value="az">Name A → Z</option>
      </select>
    </div>

    <!-- Reset -->
    <button class="pill" style="width:100%;justify-content:center;padding:8px;border-radius:var(--rad);margin-top:4px" onclick="resetFilters()">
      ↺ Reset All Filters
    </button>

    <div class="result-count">Showing <span id="result-count">0</span> products</div>

  </aside>

  <!-- ═══ MAIN CONTENT ═══ -->
  <main class="main">

    <!-- Stats -->
    <div class="stats-row">
      <div class="stat-card" style="--accent-color:var(--accent)">
        <div class="stat-label">Total Variants</div>
        <div class="stat-val" id="stat-total">{total_vars:,}</div>
        <div class="stat-sub">Across all 6 shops</div>
      </div>
      <div class="stat-card" style="--accent-color:var(--green)">
        <div class="stat-label">Unique Products</div>
        <div class="stat-val" id="stat-products">{len(products):,}</div>
        <div class="stat-sub">After deduplication</div>
      </div>
      <div class="stat-card" style="--accent-color:var(--orange)">
        <div class="stat-label">Price Gaps Found</div>
        <div class="stat-val" id="stat-gaps">{sum(1 for p in products if p['site_count']>=2):,}</div>
        <div class="stat-sub">Listed by 2+ shops</div>
      </div>
      <div class="stat-card" style="--accent-color:var(--purple)">
        <div class="stat-label">Biggest Gap</div>
        <div class="stat-val" style="font-size:18px" id="stat-maxgap">{"Rs. " + f"{max((p['spread'] for p in products),default=0):,}"}</div>
        <div class="stat-sub" id="stat-maxgap-name" style="font-size:10px">{next((p['name'][:35] for p in products if p['spread']==max((p['spread'] for p in products),default=0)),"—")}</div>
      </div>
    </div>

    <!-- Site coverage -->
    <div class="site-pills-row">{site_count_pills}</div>

    <!-- View toggle -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px">
      <div class="view-toggle">
        <button class="view-btn active" onclick="setView('grid',this)" id="btn-grid">⊞ Cards</button>
        <button class="view-btn" onclick="setView('table',this)" id="btn-table">≡ Table</button>
      </div>
      <div style="font-family:var(--font-m);font-size:11px;color:var(--muted)">
        <span style="color:var(--green)">■</span> Lowest price &nbsp;
        <span style="color:var(--red)">■</span> Highest price
      </div>
    </div>

    <!-- Product grid -->
    <div id="product-grid"></div>

    <!-- Table view (hidden by default) -->
    <div id="table-view" style="display:none">
      <div class="tbl-wrap">
        <table id="product-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Brand</th>
              <th>Storage</th>
              {''.join(f'<th class="site-th" style="color:{SITE_COLORS.get(s,"#999")}">{s}</th>' for s in SITE_ORDER)}
              <th>Gap</th>
            </tr>
          </thead>
          <tbody id="table-body"></tbody>
        </table>
      </div>
    </div>

    <!-- Empty state -->
    <div id="empty-state" style="display:none" class="empty">
      <div class="empty-icon">🔍</div>
      <div class="empty-text">No products match your filters.<br>Try adjusting or resetting.</div>
    </div>

  </main>
</div>

<script>
// ── EMBEDDED DATA ─────────────────────────────────────────────────────────────
const ALL_PRODUCTS   = {js_data};
const SITE_ORDER     = {js_sites};
const SITE_COLORS    = {js_site_colors};

// ── STATE ─────────────────────────────────────────────────────────────────────
let activeBrand   = 'all';
let activeCat     = 'all';
let activeStorage = 'all';
let activeShop    = 'all';
let currentView   = 'grid';
let filtered      = [...ALL_PRODUCTS];

// ── FILTER ENGINE ─────────────────────────────────────────────────────────────
function applyFilters() {{
  const q        = document.getElementById('search-input').value.toLowerCase().trim();
  const priceMin = parseFloat(document.getElementById('price-min').value) || 0;
  const priceMax = parseFloat(document.getElementById('price-max').value) || Infinity;
  const sortBy   = document.getElementById('sort-select').value;

  filtered = ALL_PRODUCTS.filter(p => {{
    // Search
    if (q && !p.name.toLowerCase().includes(q)) return false;
    // Brand
    if (activeBrand !== 'all' && p.brand !== activeBrand) return false;
    // Category
    if (activeCat !== 'all' && p.category !== activeCat) return false;
    // Storage
    if (activeStorage !== 'all') {{
      if (!p.storage_options.includes(activeStorage)) return false;
    }}
    // Shop
    if (activeShop !== 'all') {{
      if (!p.sites.includes(activeShop)) return false;
    }}
    // Price range — check if any variant fits
    if (priceMin > 0 || priceMax < Infinity) {{
      const hasPrice = Object.values(p.variants).some(vdata =>
        Object.values(vdata).some(info => info.price >= priceMin && info.price <= priceMax)
      );
      if (!hasPrice) return false;
    }}
    return true;
  }});

  // Sort
  filtered.sort((a, b) => {{
    if (sortBy === 'price-low')  return a.market_low - b.market_low;
    if (sortBy === 'price-high') return b.market_low - a.market_low;
    if (sortBy === 'spread')     return b.spread - a.spread;
    if (sortBy === 'az')         return a.name.localeCompare(b.name);
    return b.site_count - a.site_count;  // default: most shops first
  }});

  document.getElementById('result-count').textContent = filtered.length;
  renderView();
}}

// ── PILL FILTER HELPERS ───────────────────────────────────────────────────────
function setPill(containerId, val, type) {{
  document.querySelectorAll(`#${{containerId}} .pill`).forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  if      (type==='brand')   activeBrand   = val;
  else if (type==='cat')     activeCat     = val;
  else if (type==='storage') activeStorage = val;
  else if (type==='shop')    activeShop    = val;
  applyFilters();
}}
function filterBrand(val,btn)   {{ activeBrand=val;   syncPills('brand-pills',val);   applyFilters(); }}
function filterCat(val,btn)     {{ activeCat=val;     syncPills('cat-pills',val);     applyFilters(); }}
function filterStorage(val,btn) {{ activeStorage=val; syncPills('storage-pills',val); applyFilters(); }}
function filterShop(val,btn)    {{ activeShop=val;    syncPills('shop-pills',val);    applyFilters(); }}

function syncPills(containerId, val) {{
  document.querySelectorAll(`#${{containerId}} .pill`).forEach(b => {{
    const bval = b.textContent.trim();
    b.classList.toggle('active', bval === (val==='all'?'All':val));
  }});
}}

function resetFilters() {{
  activeBrand=activeCat=activeStorage=activeShop='all';
  document.getElementById('search-input').value='';
  document.getElementById('price-min').value='';
  document.getElementById('price-max').value='';
  document.getElementById('sort-select').value='shops';
  ['brand-pills','cat-pills','storage-pills','shop-pills'].forEach(id => {{
    const pills = document.querySelectorAll(`#${{id}} .pill`);
    pills.forEach((b,i) => b.classList.toggle('active', i===0));
  }});
  applyFilters();
}}

// ── VIEW TOGGLE ───────────────────────────────────────────────────────────────
function setView(v, btn) {{
  currentView = v;
  document.getElementById('product-grid').style.display = v==='grid' ? '' : 'none';
  document.getElementById('table-view').style.display   = v==='table' ? '' : 'none';
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderView();
}}

// ── RENDER ────────────────────────────────────────────────────────────────────
function renderView() {{
  if (currentView === 'grid') renderGrid();
  else renderTable();
  const empty = document.getElementById('empty-state');
  empty.style.display = filtered.length === 0 ? '' : 'none';
}}

function renderGrid() {{
  const grid = document.getElementById('product-grid');
  if (filtered.length === 0) {{ grid.innerHTML=''; return; }}

  grid.innerHTML = filtered.map(p => {{
    // Storage tabs
    const storages = p.storage_options;
    const defaultStorage = activeStorage !== 'all' && storages.includes(activeStorage)
      ? activeStorage : storages[0];

    const storageTabs = storages.length > 1
      ? `<div class="storage-tabs">${{storages.map(s =>
          `<button class="storage-tab${{s===defaultStorage?' active':''}}"
            onclick="switchStorage(this,'${{escJs(p.name)}}','${{escJs(s)}}')">${{s}}</button>`
        ).join('')}}</div>`
      : '';

    // Price rows for default storage
    const vdata   = p.variants[defaultStorage] || {{}};
    const prices  = Object.values(vdata).map(i=>i.price).filter(Boolean);
    const pMin    = prices.length ? Math.min(...prices) : null;
    const pMax    = prices.length ? Math.max(...prices) : null;

    const priceRows = SITE_ORDER.map(site => {{
      const info = vdata[site];
      if (!info) return `<div class="price-row">
        <span class="price-site"><span class="site-dot" style="background:${{SITE_COLORS[site]||'#555'}}"></span>${{site}}</span>
        <span class="price-na">—</span></div>`;

      const pclass = info.price===pMin && prices.length>1 ? 'price-low'
                   : info.price===pMax && prices.length>1 ? 'price-high'
                   : 'price-mid';
      const priceStr = 'Rs. ' + info.price.toLocaleString();
      const inner = `<span class="site-dot" style="background:${{SITE_COLORS[site]||'#555'}}"></span>${{site}}`;
      const val   = `<span class="price-val ${{pclass}}">${{priceStr}}</span>`;
      return info.url
        ? `<div class="price-row"><span class="price-site">${{inner}}</span><a href="${{info.url}}" target="_blank" class="price-link">${{val}}</a></div>`
        : `<div class="price-row"><span class="price-site">${{inner}}</span>${{val}}</div>`;
    }}).join('');

    const spreadHtml = p.site_count > 1
      ? `<div class="spread-bar">
          <span>Price gap across shops</span>
          <span class="spread-val">Rs. ${{p.spread.toLocaleString()}} (${{p.spread_pct}}%)</span>
        </div>` : '';

    const sitesBadge = `<span class="sites-badge">${{p.site_count}} shop${{p.site_count!==1?'s':''}}</span>`;

    return `<div class="product-card" data-name="${{escJs(p.name)}}">
      <div class="card-header">
        <div class="card-brand">${{p.brand}}</div>
        <div class="card-name">${{p.name}}</div>
        <div class="card-meta">
          <span class="cat-badge">${{p.category}}</span>
          ${{sitesBadge}}
        </div>
      </div>
      ${{storageTabs}}
      <div class="price-rows" id="pr-${{safeId(p.name)}}-${{safeId(defaultStorage)}}">${{priceRows}}</div>
      ${{spreadHtml}}
    </div>`;
  }}).join('');
}}

function renderTable() {{
  const tbody = document.getElementById('table-body');
  if (filtered.length===0) {{ tbody.innerHTML=''; return; }}

  tbody.innerHTML = filtered.flatMap(p => {{
    return p.storage_options.map(storage => {{
      const vdata  = p.variants[storage] || {{}};
      const prices = Object.values(vdata).map(i=>i.price).filter(Boolean);
      const pMin   = prices.length ? Math.min(...prices) : null;
      const pMax   = prices.length ? Math.max(...prices) : null;

      const cells = SITE_ORDER.map(site => {{
        const info = vdata[site];
        if (!info) return `<td class="tbl-price"><span style="color:var(--dim)">—</span></td>`;
        const col = info.price===pMin && prices.length>1 ? 'var(--green)'
                  : info.price===pMax && prices.length>1 ? 'var(--red)'
                  : 'var(--text)';
        const val = `<span style="color:${{col}}">Rs. ${{info.price.toLocaleString()}}</span>`;
        return info.url
          ? `<td class="tbl-price"><a href="${{info.url}}" target="_blank" style="text-decoration:none">${{val}}</a></td>`
          : `<td class="tbl-price">${{val}}</td>`;
      }}).join('');

      const spread = prices.length>1
        ? `<span style="color:var(--orange);font-family:var(--font-m);font-size:11px">Rs. ${{(pMax-pMin).toLocaleString()}}</span>`
        : '<span style="color:var(--dim);font-size:11px">—</span>';

      return `<tr>
        <td><div class="tbl-name">${{p.name}}</div></td>
        <td class="tbl-brand">${{p.brand}}</td>
        <td style="font-family:var(--font-m);font-size:11px;color:var(--muted)">${{storage}}</td>
        ${{cells}}
        <td style="text-align:right">${{spread}}</td>
      </tr>`;
    }});
  }}).join('');
}}

// ── STORAGE SWITCH on card ────────────────────────────────────────────────────
function switchStorage(btn, productName, storage) {{
  // Update tab active state
  const card = btn.closest('.product-card');
  card.querySelectorAll('.storage-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  // Find product
  const p = ALL_PRODUCTS.find(x => x.name === productName);
  if (!p) return;

  const vdata  = p.variants[storage] || {{}};
  const prices = Object.values(vdata).map(i=>i.price).filter(Boolean);
  const pMin   = prices.length ? Math.min(...prices) : null;
  const pMax   = prices.length ? Math.max(...prices) : null;

  const rows = SITE_ORDER.map(site => {{
    const info = vdata[site];
    if (!info) return `<div class="price-row">
      <span class="price-site"><span class="site-dot" style="background:${{SITE_COLORS[site]||'#555'}}"></span>${{site}}</span>
      <span class="price-na">—</span></div>`;
    const pclass = info.price===pMin && prices.length>1 ? 'price-low'
                 : info.price===pMax && prices.length>1 ? 'price-high'
                 : 'price-mid';
    const val = `<span class="price-val ${{pclass}}">Rs. ${{info.price.toLocaleString()}}</span>`;
    return info.url
      ? `<div class="price-row"><span class="price-site"><span class="site-dot" style="background:${{SITE_COLORS[site]||'#555'}}"></span>${{site}}</span><a href="${{info.url}}" target="_blank" class="price-link">${{val}}</a></div>`
      : `<div class="price-row"><span class="price-site"><span class="site-dot" style="background:${{SITE_COLORS[site]||'#555'}}"></span>${{site}}</span>${{val}}</div>`;
  }}).join('');

  const priceDiv = card.querySelector('.price-rows');
  if (priceDiv) priceDiv.innerHTML = rows;
}}

// ── UTILS ─────────────────────────────────────────────────────────────────────
function escJs(s)  {{ return (s||'').replace(/'/g,"\\'").replace(/"/g,'&quot;'); }}
function safeId(s) {{ return (s||'').replace(/[^a-z0-9]/gi,'_'); }}

// ── INIT ──────────────────────────────────────────────────────────────────────
applyFilters();
</script>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open",     action="store_true")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    global DATA_DIR
    DATA_DIR = Path(args.data_dir)

    records, date_str = load_latest()
    html = generate_html(records, date_str)

    out_path = DATA_DIR / f"report_{date_str}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # GitHub Actions env
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"REPORT_DATE={date_str}\n")

    print(f"\n✓  Dashboard: {out_path}")
    print(f"   Records : {len(records):,}  |  Date: {date_str}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{out_path.resolve()}")

    return out_path


if __name__ == "__main__":
    main()
