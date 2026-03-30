"""
dashboard.py — Idealz.lk Live Price Intelligence Dashboard (v5 fixed)
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
    "Anker":       ["anker", "soundcore"],
    "DJI":         ["dji", "osmo", "insta360"],
    "PlayStation": ["playstation", "ps5"],
    "Dyson":       ["dyson"],
    "Other":       [],
}

CATEGORY_KEYWORDS = {
    "Smartphones":   ["iphone", "galaxy", "pixel", "oneplus", "xiaomi", "redmi", "oppo", "realme", "vivo", "infinix", "tecno", "honor", "nokia", "nothing"],
    "MacBooks":      ["macbook"],
    "iPads":         ["ipad"],
    "Tablets":       ["tab ", "tablet"],
    "Smart Watches": ["watch", "band"],
    "Earbuds":       ["airpod", "buds", "earbuds", "earbud", "wf-", "soundcore", "cmf buds"],
    "Headphones":    ["headphone", "wh-", "wh1000", "xm5", "xm6"],
    "Speakers":      ["speaker", "jbl", "soundbar"],
    "Laptops":       ["laptop", "notebook"],
    "Gaming":        ["playstation", "ps5", "xbox", "meta quest"],
    "Cameras":       ["dji", "osmo", "insta360", "gopro"],
    "Accessories":   ["case", "charger", "cable", "adapter", "screen"],
    "Other":         [],
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
    if not variant:
        return ""
    m = re.search(r"(\d+\s*(?:GB|TB))", variant, re.IGNORECASE)
    if m:
        return m.group(1).replace(" ", "").upper()
    return ""


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
    products = {}

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
        pkey     = name.lower().strip()

        if pkey not in products:
            products[pkey] = {
                "name":     name,
                "brand":    brand,
                "category": category,
                "variants": {},
            }

        p    = products[pkey]
        vkey = storage or variant or "Standard"

        if vkey not in p["variants"]:
            p["variants"][vkey] = {}

        existing = p["variants"][vkey].get(site)
        if existing is None or price < existing["price"]:
            p["variants"][vkey][site] = {"price": price, "url": url}

    result = []
    for pkey, p in products.items():
        all_p = [
            info["price"]
            for vdata in p["variants"].values()
            for info in vdata.values()
        ]
        if not all_p:
            continue

        sites_carrying = set()
        for vdata in p["variants"].values():
            sites_carrying.update(vdata.keys())

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


def make_pills(items, js_fn):
    """Build filter pill HTML — avoids quote-inside-f-string errors."""
    parts = ['<button class="pill active" onclick="' + js_fn + '(\'all\',this)">All</button>']
    for item in items:
        safe = item.replace("'", "").replace('"', "")
        parts.append(
            '<button class="pill" onclick="' + js_fn + '(\'' + safe + '\',this)">' + item + '</button>'
        )
    return "\n".join(parts)


def generate_html(records, date_str):
    products   = process(records)
    fmt_date   = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    total_vars = len(records)

    site_counts = defaultdict(int)
    for r in records:
        site_counts[r.get("site", "")] += 1

    all_brands     = sorted(set(p["brand"]    for p in products))
    all_categories = sorted(set(p["category"] for p in products))

    def storage_sort_key(x):
        m = re.search(r"\d+", x)
        n = int(m.group()) if m else 0
        if "TB" in x.upper():
            return (2, n)
        if n < 100:
            return (0, n)
        return (1, n)

    all_storages = sorted(
        set(s for p in products for s in p["storage_options"] if s and s != "Standard"),
        key=storage_sort_key
    )

    # --- Build filter pills using the safe helper ---
    brand_pills   = make_pills(all_brands,   "filterBrand")
    cat_pills     = make_pills(all_categories, "filterCat")
    storage_pills = make_pills(all_storages, "filterStorage")
    shop_pills    = make_pills(SITE_ORDER,   "filterShop")

    # --- Site coverage pills ---
    site_count_html = ""
    for site in SITE_ORDER:
        c   = site_counts.get(site, 0)
        col = SITE_COLORS.get(site, "#999")
        site_count_html += (
            '<div class="site-pill" style="border-top-color:' + col + '">'
            '<div class="site-pill-name" style="color:' + col + '">' + site + '</div>'
            '<div class="site-pill-count">' + f"{c:,}" + '</div>'
            '<div class="site-pill-label">variants</div>'
            '</div>'
        )

    # --- Table header site columns ---
    site_th_html = ""
    for s in SITE_ORDER:
        col = SITE_COLORS.get(s, "#999")
        site_th_html += '<th class="site-th" style="color:' + col + '">' + s + '</th>'

    # --- Stat card values ---
    max_spread     = max((p["spread"] for p in products), default=0)
    max_spread_str = "Rs. " + f"{max_spread:,}"
    max_spread_name = next(
        (p["name"][:35] for p in products if p["spread"] == max_spread), "—"
    )
    gap_count = sum(1 for p in products if p["site_count"] >= 2)

    # --- Embed data ---
    js_data        = json.dumps(products,    ensure_ascii=False)
    js_sites       = json.dumps(SITE_ORDER)
    js_site_colors = json.dumps(SITE_COLORS)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idealz.lk — Price Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#07090f;--s1:#0d1117;--s2:#161b22;--s3:#21262d;--border:#30363d;
  --accent:#58a6ff;--green:#3fb950;--red:#f85149;--orange:#d29922;
  --purple:#bc8cff;--text:#e6edf3;--muted:#7d8590;--dim:#484f58;
  --font-d:'Syne',sans-serif;--font-b:'DM Sans',sans-serif;--font-m:'DM Mono',monospace;
  --rad:8px;--rad-lg:12px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--font-b);min-height:100vh;font-size:14px}
.topbar{background:rgba(13,17,23,.95);border-bottom:1px solid var(--border);padding:14px 28px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:200;backdrop-filter:blur(12px)}
.logo{font-family:var(--font-d);font-size:18px;font-weight:800;letter-spacing:-0.5px}
.logo em{font-style:normal;color:var(--accent)}
.topbar-right{display:flex;align-items:center;gap:12px}
.badge{font-family:var(--font-m);font-size:10px;padding:3px 10px;border-radius:20px;letter-spacing:.5px}
.badge-blue{background:rgba(88,166,255,.1);color:var(--accent);border:1px solid rgba(88,166,255,.25)}
.badge-green{background:rgba(63,185,80,.1);color:var(--green);border:1px solid rgba(63,185,80,.25)}
.topbar-date{font-family:var(--font-m);font-size:10px;color:var(--muted)}
.layout{display:grid;grid-template-columns:260px 1fr;min-height:calc(100vh - 53px)}
.sidebar{background:var(--s1);border-right:1px solid var(--border);padding:20px 16px;
  position:sticky;top:53px;height:calc(100vh - 53px);overflow-y:auto}
.sidebar::-webkit-scrollbar{width:4px}
.sidebar::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.filter-section{margin-bottom:22px}
.filter-label{font-family:var(--font-m);font-size:10px;color:var(--muted);letter-spacing:1.5px;
  text-transform:uppercase;margin-bottom:9px;display:block}
.search-wrap{position:relative;margin-bottom:20px}
.search-wrap input{width:100%;background:var(--s2);border:1px solid var(--border);
  border-radius:var(--rad);color:var(--text);font-family:var(--font-b);font-size:13px;
  padding:9px 12px 9px 34px;outline:none;transition:border-color .15s}
.search-wrap input:focus{border-color:var(--accent)}
.search-wrap input::placeholder{color:var(--dim)}
.search-icon{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--dim);font-size:14px}
.pill-wrap{display:flex;flex-wrap:wrap;gap:5px}
.pill{font-size:11px;font-family:var(--font-m);padding:4px 10px;border-radius:20px;
  border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;
  transition:all .15s;white-space:nowrap}
.pill:hover{border-color:var(--accent);color:var(--accent)}
.pill.active{background:rgba(88,166,255,.12);border-color:var(--accent);color:var(--accent)}
.range-wrap{display:flex;gap:8px;align-items:center}
.range-wrap input[type=number]{flex:1;background:var(--s2);border:1px solid var(--border);
  border-radius:var(--rad);color:var(--text);font-family:var(--font-m);font-size:12px;padding:7px 10px;outline:none}
.range-wrap input:focus{border-color:var(--accent)}
.range-sep{color:var(--muted);font-size:12px}
.sort-select{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:var(--rad);
  color:var(--text);font-family:var(--font-b);font-size:13px;padding:8px 10px;outline:none;cursor:pointer}
.result-count{font-family:var(--font-m);font-size:11px;color:var(--muted);margin-top:14px;text-align:center}
.result-count span{color:var(--accent);font-weight:500}
.main{padding:24px;overflow-y:auto}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.stat-card{background:var(--s1);border:1px solid var(--border);border-radius:var(--rad-lg);
  padding:16px 18px;position:relative;overflow:hidden}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac,var(--accent))}
.stat-label{font-family:var(--font-m);font-size:10px;color:var(--muted);letter-spacing:1px;
  text-transform:uppercase;margin-bottom:8px}
.stat-val{font-family:var(--font-d);font-size:26px;font-weight:800;color:var(--ac,var(--accent));
  letter-spacing:-1px;line-height:1}
.stat-sub{font-size:11px;color:var(--muted);margin-top:4px}
.site-pills-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}
.site-pill{background:var(--s1);border:1px solid var(--border);border-radius:var(--rad-lg);
  padding:12px 16px;border-top:3px solid;text-align:center;min-width:110px}
.site-pill-name{font-family:var(--font-m);font-size:9px;font-weight:500;letter-spacing:.5px;
  text-transform:uppercase;margin-bottom:4px}
.site-pill-count{font-family:var(--font-d);font-size:20px;font-weight:800;color:var(--text);line-height:1}
.site-pill-label{font-size:10px;color:var(--muted);margin-top:2px}
.view-toggle{display:flex;gap:4px;margin-bottom:20px}
.view-btn{font-family:var(--font-m);font-size:11px;padding:6px 14px;border:1px solid var(--border);
  border-radius:var(--rad);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s}
.view-btn.active{background:rgba(88,166,255,.1);border-color:var(--accent);color:var(--accent)}
#product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
.product-card{background:var(--s1);border:1px solid var(--border);border-radius:var(--rad-lg);
  overflow:hidden;transition:border-color .2s,transform .2s;animation:fadeIn .3s ease}
.product-card:hover{border-color:rgba(88,166,255,.4);transform:translateY(-2px)}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.card-header{padding:14px 16px 10px;border-bottom:1px solid var(--s3)}
.card-brand{font-family:var(--font-m);font-size:10px;color:var(--muted);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:4px}
.card-name{font-size:14px;font-weight:600;color:var(--text);line-height:1.3}
.card-meta{display:flex;align-items:center;gap:8px;margin-top:6px}
.cat-badge{font-family:var(--font-m);font-size:9px;padding:2px 7px;border-radius:20px;
  background:var(--s3);color:var(--muted);border:1px solid var(--border)}
.sites-badge{font-family:var(--font-m);font-size:9px;padding:2px 7px;border-radius:20px;
  border:1px solid rgba(88,166,255,.3);color:var(--accent);background:rgba(88,166,255,.08)}
.storage-tabs{display:flex;gap:4px;padding:10px 16px 0;flex-wrap:wrap}
.storage-tab{font-family:var(--font-m);font-size:10px;padding:3px 9px;border-radius:4px;
  border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .12s}
.storage-tab:hover{border-color:var(--accent);color:var(--accent)}
.storage-tab.active{background:rgba(88,166,255,.12);border-color:var(--accent);color:var(--accent)}
.price-rows{padding:10px 16px 14px}
.price-row{display:flex;align-items:center;justify-content:space-between;
  padding:6px 0;border-bottom:1px solid var(--s3)}
.price-row:last-child{border-bottom:none}
.price-site{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted)}
.site-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.price-val{font-family:var(--font-m);font-size:13px;font-weight:500}
.price-low{color:var(--green)}.price-high{color:var(--red)}.price-mid{color:var(--text)}
.price-na{color:var(--dim);font-size:11px}
.price-link{text-decoration:none;color:inherit}
.price-link:hover .price-val{text-decoration:underline}
.spread-bar{margin:8px 16px 0;padding:8px 10px;background:var(--s2);border-radius:var(--rad);
  display:flex;align-items:center;justify-content:space-between;font-family:var(--font-m);
  font-size:10px;color:var(--muted)}
.spread-val{color:var(--orange);font-weight:500}
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--rad-lg)}
#product-table{width:100%;border-collapse:collapse;min-width:800px}
#product-table thead tr{background:var(--s2)}
#product-table th{padding:10px 12px;text-align:left;font-family:var(--font-m);font-size:9px;
  color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;border-bottom:1px solid var(--border);white-space:nowrap}
#product-table .site-th{text-align:right}
#product-table tbody tr{border-bottom:1px solid rgba(48,54,61,.5);transition:background .1s}
#product-table tbody tr:hover{background:rgba(88,166,255,.03)}
#product-table td{padding:10px 12px;vertical-align:middle;font-size:12px}
.tbl-name{font-weight:500;font-size:13px}
.tbl-price{font-family:var(--font-m);font-size:12px;text-align:right;white-space:nowrap}
.empty{text-align:center;padding:60px 20px;color:var(--muted)}
.empty-icon{font-size:40px;margin-bottom:12px}
@media(max-width:900px){.layout{grid-template-columns:1fr}.sidebar{position:static;height:auto;
  border-right:none;border-bottom:1px solid var(--border)}.stats-row{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.topbar{padding:12px 14px}.main{padding:14px}
  .stats-row{grid-template-columns:1fr 1fr}#product-grid{grid-template-columns:1fr}}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo"><em>Idealz</em>.lk &mdash; Price Intelligence</div>
  <div class="topbar-right">
    <span class="badge badge-green">LIVE</span>
    <span class="badge badge-blue">""" + f"{total_vars:,}" + """ VARIANTS</span>
    <span class="topbar-date">""" + fmt_date.upper() + """</span>
  </div>
</div>

<div class="layout">
<aside class="sidebar">
  <div class="search-wrap">
    <span class="search-icon">&#9906;</span>
    <input type="text" id="search-input" placeholder="Search product..." oninput="applyFilters()">
  </div>
  <div class="filter-section">
    <span class="filter-label">Brand</span>
    <div class="pill-wrap" id="brand-pills">""" + brand_pills + """</div>
  </div>
  <div class="filter-section">
    <span class="filter-label">Category</span>
    <div class="pill-wrap" id="cat-pills">""" + cat_pills + """</div>
  </div>
  <div class="filter-section">
    <span class="filter-label">Storage</span>
    <div class="pill-wrap" id="storage-pills">""" + storage_pills + """</div>
  </div>
  <div class="filter-section">
    <span class="filter-label">Shop</span>
    <div class="pill-wrap" id="shop-pills">""" + shop_pills + """</div>
  </div>
  <div class="filter-section">
    <span class="filter-label">Price Range (LKR)</span>
    <div class="range-wrap">
      <input type="number" id="price-min" placeholder="Min" oninput="applyFilters()" step="10000">
      <span class="range-sep">&mdash;</span>
      <input type="number" id="price-max" placeholder="Max" oninput="applyFilters()" step="10000">
    </div>
  </div>
  <div class="filter-section">
    <span class="filter-label">Sort By</span>
    <select class="sort-select" id="sort-select" onchange="applyFilters()">
      <option value="shops">Most shops first</option>
      <option value="price-low">Price: Low to High</option>
      <option value="price-high">Price: High to Low</option>
      <option value="spread">Biggest price gap</option>
      <option value="az">Name A &rarr; Z</option>
    </select>
  </div>
  <button class="pill" style="width:100%;padding:8px;border-radius:var(--rad);margin-top:4px" onclick="resetFilters()">
    &#8635; Reset All Filters
  </button>
  <div class="result-count">Showing <span id="result-count">0</span> products</div>
</aside>

<main class="main">
  <div class="stats-row">
    <div class="stat-card" style="--ac:var(--accent)">
      <div class="stat-label">Total Variants</div>
      <div class="stat-val">""" + f"{total_vars:,}" + """</div>
      <div class="stat-sub">Across all 6 shops</div>
    </div>
    <div class="stat-card" style="--ac:var(--green)">
      <div class="stat-label">Unique Products</div>
      <div class="stat-val">""" + f"{len(products):,}" + """</div>
      <div class="stat-sub">After deduplication</div>
    </div>
    <div class="stat-card" style="--ac:var(--orange)">
      <div class="stat-label">Price Gaps Found</div>
      <div class="stat-val">""" + f"{gap_count:,}" + """</div>
      <div class="stat-sub">Listed by 2+ shops</div>
    </div>
    <div class="stat-card" style="--ac:var(--purple)">
      <div class="stat-label">Biggest Gap</div>
      <div class="stat-val" style="font-size:18px">""" + max_spread_str + """</div>
      <div class="stat-sub" style="font-size:10px">""" + max_spread_name + """</div>
    </div>
  </div>

  <div class="site-pills-row">""" + site_count_html + """</div>

  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px">
    <div class="view-toggle">
      <button class="view-btn active" onclick="setView('grid',this)">&#8862; Cards</button>
      <button class="view-btn" onclick="setView('table',this)">&#8801; Table</button>
    </div>
    <div style="font-family:var(--font-m);font-size:11px;color:var(--muted)">
      <span style="color:var(--green)">&#9632;</span> Lowest &nbsp;
      <span style="color:var(--red)">&#9632;</span> Highest
    </div>
  </div>

  <div id="product-grid"></div>

  <div id="table-view" style="display:none">
    <div class="tbl-wrap">
      <table id="product-table">
        <thead><tr>
          <th>Product</th><th>Brand</th><th>Storage</th>
          """ + site_th_html + """
          <th style="text-align:right">Gap</th>
        </tr></thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
  </div>

  <div id="empty-state" style="display:none" class="empty">
    <div class="empty-icon">&#128269;</div>
    <div>No products match your filters. Try resetting.</div>
  </div>
</main>
</div>

<script>
const ALL_PRODUCTS = """ + js_data + """;
const SITE_ORDER   = """ + js_sites + """;
const SITE_COLORS  = """ + js_site_colors + """;

let activeBrand='all', activeCat='all', activeStorage='all', activeShop='all';
let currentView='grid', filtered=[...ALL_PRODUCTS];

function applyFilters(){
  const q=document.getElementById('search-input').value.toLowerCase().trim();
  const mn=parseFloat(document.getElementById('price-min').value)||0;
  const mx=parseFloat(document.getElementById('price-max').value)||Infinity;
  const sort=document.getElementById('sort-select').value;

  filtered=ALL_PRODUCTS.filter(p=>{
    if(q && !p.name.toLowerCase().includes(q)) return false;
    if(activeBrand!=='all' && p.brand!==activeBrand) return false;
    if(activeCat!=='all'   && p.category!==activeCat) return false;
    if(activeStorage!=='all' && !p.storage_options.includes(activeStorage)) return false;
    if(activeShop!=='all'    && !p.sites.includes(activeShop)) return false;
    if(mn>0||mx<Infinity){
      const ok=Object.values(p.variants).some(vd=>Object.values(vd).some(i=>i.price>=mn&&i.price<=mx));
      if(!ok) return false;
    }
    return true;
  });

  filtered.sort((a,b)=>{
    if(sort==='price-low')  return a.market_low-b.market_low;
    if(sort==='price-high') return b.market_low-a.market_low;
    if(sort==='spread')     return b.spread-a.spread;
    if(sort==='az')         return a.name.localeCompare(b.name);
    return b.site_count-a.site_count;
  });

  document.getElementById('result-count').textContent=filtered.length;
  renderView();
}

function syncPills(id,val){
  document.querySelectorAll('#'+id+' .pill').forEach(b=>{
    b.classList.toggle('active', b.textContent.trim()===(val==='all'?'All':val));
  });
}
function filterBrand(v)  {activeBrand=v;   syncPills('brand-pills',v);   applyFilters();}
function filterCat(v)    {activeCat=v;     syncPills('cat-pills',v);     applyFilters();}
function filterStorage(v){activeStorage=v; syncPills('storage-pills',v); applyFilters();}
function filterShop(v)   {activeShop=v;    syncPills('shop-pills',v);    applyFilters();}

function resetFilters(){
  activeBrand=activeCat=activeStorage=activeShop='all';
  document.getElementById('search-input').value='';
  document.getElementById('price-min').value='';
  document.getElementById('price-max').value='';
  document.getElementById('sort-select').value='shops';
  ['brand-pills','cat-pills','storage-pills','shop-pills'].forEach(id=>{
    document.querySelectorAll('#'+id+' .pill').forEach((b,i)=>b.classList.toggle('active',i===0));
  });
  applyFilters();
}

function setView(v,btn){
  currentView=v;
  document.getElementById('product-grid').style.display=v==='grid'?'':'none';
  document.getElementById('table-view').style.display=v==='table'?'':'none';
  document.querySelectorAll('.view-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderView();
}

function renderView(){
  if(currentView==='grid') renderGrid(); else renderTable();
  document.getElementById('empty-state').style.display=filtered.length===0?'':'none';
}

function priceRows(vdata){
  const prices=Object.values(vdata).map(i=>i.price).filter(Boolean);
  const pMin=prices.length?Math.min(...prices):null;
  const pMax=prices.length?Math.max(...prices):null;
  return SITE_ORDER.map(site=>{
    const info=vdata[site];
    const dot='<span class="site-dot" style="background:'+(SITE_COLORS[site]||'#555')+'"></span>';
    if(!info) return '<div class="price-row"><span class="price-site">'+dot+site+'</span><span class="price-na">&#8212;</span></div>';
    const cls=info.price===pMin&&prices.length>1?'price-low':info.price===pMax&&prices.length>1?'price-high':'price-mid';
    const str='Rs. '+info.price.toLocaleString();
    const val='<span class="price-val '+cls+'">'+str+'</span>';
    const inner=info.url?'<a href="'+info.url+'" target="_blank" class="price-link">'+val+'</a>':val;
    return '<div class="price-row"><span class="price-site">'+dot+site+'</span>'+inner+'</div>';
  }).join('');
}

function renderGrid(){
  const grid=document.getElementById('product-grid');
  if(filtered.length===0){grid.innerHTML='';return;}
  grid.innerHTML=filtered.map(p=>{
    const storages=p.storage_options;
    const defStorage=activeStorage!=='all'&&storages.includes(activeStorage)?activeStorage:storages[0];
    const tabs=storages.length>1
      ?'<div class="storage-tabs">'+storages.map(s=>{
          const ac=s===defStorage?' active':'';
          return '<button class="storage-tab'+ac+'" onclick="switchStorage(this,\''+esc(p.name)+'\',\''+esc(s)+'\')">'+s+'</button>';
        }).join('')+'</div>'
      :'';
    const vdata=p.variants[defStorage]||{};
    const prices=Object.values(vdata).map(i=>i.price).filter(Boolean);
    const spread=p.site_count>1
      ?'<div class="spread-bar"><span>Price gap</span><span class="spread-val">Rs. '+p.spread.toLocaleString()+' ('+p.spread_pct+'%)</span></div>'
      :'';
    return '<div class="product-card">'
      +'<div class="card-header">'
      +'<div class="card-brand">'+p.brand+'</div>'
      +'<div class="card-name">'+p.name+'</div>'
      +'<div class="card-meta">'
      +'<span class="cat-badge">'+p.category+'</span>'
      +'<span class="sites-badge">'+p.site_count+' shop'+(p.site_count!==1?'s':'')+'</span>'
      +'</div></div>'
      +tabs
      +'<div class="price-rows" id="pr-'+sid(p.name)+'">'+priceRows(vdata)+'</div>'
      +spread+'</div>';
  }).join('');
}

function switchStorage(btn,productName,storage){
  btn.closest('.product-card').querySelectorAll('.storage-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const p=ALL_PRODUCTS.find(x=>x.name===productName);
  if(!p) return;
  const el=btn.closest('.product-card').querySelector('.price-rows');
  if(el) el.innerHTML=priceRows(p.variants[storage]||{});
}

function renderTable(){
  const tbody=document.getElementById('table-body');
  if(filtered.length===0){tbody.innerHTML='';return;}
  tbody.innerHTML=filtered.flatMap(p=>
    p.storage_options.map(storage=>{
      const vdata=p.variants[storage]||{};
      const prices=Object.values(vdata).map(i=>i.price).filter(Boolean);
      const pMin=prices.length?Math.min(...prices):null;
      const pMax=prices.length?Math.max(...prices):null;
      const cells=SITE_ORDER.map(site=>{
        const info=vdata[site];
        if(!info) return '<td class="tbl-price"><span style="color:var(--dim)">&#8212;</span></td>';
        const col=info.price===pMin&&prices.length>1?'var(--green)':info.price===pMax&&prices.length>1?'var(--red)':'var(--text)';
        const val='<span style="color:'+col+'">Rs. '+info.price.toLocaleString()+'</span>';
        return '<td class="tbl-price">'+(info.url?'<a href="'+info.url+'" target="_blank" style="text-decoration:none">'+val+'</a>':val)+'</td>';
      }).join('');
      const gap=prices.length>1?'<span style="color:var(--orange);font-family:var(--font-m);font-size:11px">Rs. '+(pMax-pMin).toLocaleString()+'</span>':'<span style="color:var(--dim)">&#8212;</span>';
      return '<tr><td><div class="tbl-name">'+p.name+'</div></td><td style="font-family:var(--font-m);font-size:10px;color:var(--muted)">'+p.brand+'</td><td style="font-family:var(--font-m);font-size:11px;color:var(--muted)">'+storage+'</td>'+cells+'<td style="text-align:right">'+gap+'</td></tr>';
    })
  ).join('');
}

function esc(s){return(s||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");}
function sid(s){return(s||'').replace(/[^a-z0-9]/gi,'_');}

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
