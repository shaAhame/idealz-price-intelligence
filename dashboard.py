"""
dashboard.py — Idealz.lk Price Intelligence Dashboard (v6 — all filters working)
==================================================================================
Fixes in v6:
  - Filters actually work when clicked (Brand, Category, Storage, Shop)
  - Storage filter only shows GB/TB values — colours are stripped out
  - Cards render immediately on page load
  - Search, sort, price range all working
  - esc() function fixed — no more silent JS errors
  - Also exports dashboard.json for Netlify frontend

Outputs:
  data/report_YYYY-MM-DD.html   — self-contained offline dashboard
  data/dashboard.html           — copy for GitHub Pages (fixed URL)
  data/dashboard.json           — data feed for Netlify website
"""

import json
import os
import re
import sys
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
    "Apple":       ["iphone", "ipad", "macbook", "airpod", "apple watch", "imac", "mac mini", "mac studio"],
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


# ── HELPERS ───────────────────────────────────────────────────────────────────

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
    """
    Extract ONLY the storage/RAM size from a variant string.
    '256GB / Midnight Black'  → '256GB'
    '8GB RAM / 256GB'         → '256GB'   (keeps the storage, not RAM)
    '512GB'                   → '512GB'
    'Cosmic Orange'           → ''        (no storage — returns empty)
    'Standard'                → ''
    """
    if not variant:
        return ""
    # Find all GB/TB values
    matches = re.findall(r"(\d+)\s*(GB|TB)", variant, re.IGNORECASE)
    if not matches:
        return ""
    # If multiple matches (e.g. 8GB RAM + 256GB storage), pick the largest
    # because storage is always larger than RAM
    best = None
    best_val = 0
    for num, unit in matches:
        n = int(num)
        # TB counts as very large
        effective = n * 1000 if unit.upper() == "TB" else n
        if effective > best_val:
            best_val = effective
            best = f"{num}{unit.upper()}"
    return best or ""


def has_storage(variant):
    """Returns True if variant contains a storage/capacity value."""
    return bool(re.search(r"\d+\s*(?:GB|TB)", variant, re.IGNORECASE))


def storage_sort_key(x):
    m = re.search(r"(\d+)", x)
    n = int(m.group(1)) if m else 0
    if "TB" in x.upper():
        return (2, n)
    if n < 100:
        return (0, n)
    return (1, n)


def load_latest():
    files = sorted(DATA_DIR.glob("prices_*.json"), reverse=True)
    if not files:
        print("No data files found. Run scraper.py first.")
        sys.exit(1)
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    date_str = files[0].stem.replace("prices_", "")
    return data, date_str


# ── DATA PROCESSING ───────────────────────────────────────────────────────────

def process(records):
    """
    Groups records into products with variants.
    Each product has:
      variants: { storage_key: { site: { price, url } } }

    The storage_key is:
      - The GB/TB value if the variant contains one  e.g. "256GB"
      - "Standard" if the variant has no storage    e.g. colour-only variant
    """
    products = {}

    for r in records:
        name    = r.get("name", "").strip()
        variant = r.get("variant", "").strip()
        price   = r.get("price")
        site    = r.get("site", "").strip()
        url     = r.get("url", "")

        if not name or not price or not site:
            continue
        if not (1000 <= price <= 5000000):
            continue

        brand    = detect_brand(name)
        category = detect_category(name)

        # Key for grouping: product name only
        pkey = name.lower().strip()

        if pkey not in products:
            products[pkey] = {
                "name":     name,
                "brand":    brand,
                "category": category,
                "variants": {},   # storage_key → { site → {price, url} }
            }

        p = products[pkey]

        # Use storage size as the variant key; fall back to "Standard"
        storage_key = extract_storage(variant) or "Standard"

        if storage_key not in p["variants"]:
            p["variants"][storage_key] = {}

        existing = p["variants"][storage_key].get(site)
        if existing is None or price < existing["price"]:
            p["variants"][storage_key][site] = {"price": price, "url": url}

    # Build result list with summary stats
    result = []
    for pkey, p in products.items():
        all_prices = [
            info["price"]
            for vdata in p["variants"].values()
            for info in vdata.values()
        ]
        if not all_prices:
            continue

        sites_carrying = set()
        for vdata in p["variants"].values():
            sites_carrying.update(vdata.keys())

        # Sort storage options properly: 128GB < 256GB < 512GB < 1TB < 2TB
        raw_keys = list(p["variants"].keys())
        storage_keys = sorted(
            [k for k in raw_keys if k != "Standard"],
            key=storage_sort_key
        )
        if "Standard" in raw_keys:
            storage_keys.append("Standard")

        market_low  = min(all_prices)
        market_high = max(all_prices)

        result.append({
            "name":            p["name"],
            "brand":           p["brand"],
            "category":        p["category"],
            "variants":        p["variants"],
            "storage_options": storage_keys,
            "sites":           sorted(sites_carrying),
            "site_count":      len(sites_carrying),
            "market_low":      market_low,
            "market_high":     market_high,
            "spread":          market_high - market_low,
            "spread_pct":      round((market_high - market_low) / market_low * 100, 1) if market_low else 0,
        })

    result.sort(key=lambda x: (-x["site_count"], x["name"].lower()))
    return result


# ── JSON EXPORT (for Netlify) ─────────────────────────────────────────────────

def export_json(records, products, date_str):
    site_counts = defaultdict(int)
    for r in records:
        site_counts[r.get("site", "")] += 1

    payload = {
        "date":        date_str,
        "generated":   datetime.now().isoformat(),
        "site_counts": dict(site_counts),
        "total":       len(records),
        "products":    products,
    }

    out = DATA_DIR / "dashboard.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(f"  ✓ dashboard.json  ({len(products)} products)")
    return out


# ── HTML GENERATOR ────────────────────────────────────────────────────────────

def generate_html(records, date_str):
    products   = process(records)
    fmt_date   = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    total_vars = len(records)

    site_counts = defaultdict(int)
    for r in records:
        site_counts[r.get("site", "")] += 1

    all_brands     = sorted(set(p["brand"]    for p in products))
    all_categories = sorted(set(p["category"] for p in products))

    # Only show real storage values (GB/TB) in the storage filter — no colours
    all_storages = sorted(
        set(
            s for p in products
            for s in p["storage_options"]
            if s and s != "Standard" and has_storage(s)
        ),
        key=storage_sort_key
    )

    # ── Site coverage chips ───────────────────────────────────────────────────
    site_chips_html = ""
    for site in SITE_ORDER:
        c   = site_counts.get(site, 0)
        col = SITE_COLORS.get(site, "#888")
        site_chips_html += (
            '<div class="schip" style="border-color:' + col + ';color:' + col + '"'
            ' onclick="filterShop(\'' + site.replace("'", "") + '\')">'
            '<span class="sdot2" style="background:' + col + '"></span>'
            + site +
            '<span class="scount">' + f"{c:,}" + '</span>'
            '</div>'
        )

    # ── Table header ──────────────────────────────────────────────────────────
    site_th_html = ""
    for s in SITE_ORDER:
        col = SITE_COLORS.get(s, "#888")
        site_th_html += '<th class="r" style="color:' + col + '">' + s + '</th>'

    # ── Stats ─────────────────────────────────────────────────────────────────
    max_spread      = max((p["spread"] for p in products), default=0)
    max_spread_str  = "Rs. " + f"{max_spread:,}"
    max_spread_name = next((p["name"][:32] for p in products if p["spread"] == max_spread), "—")
    gap_count       = sum(1 for p in products if p["site_count"] >= 2)

    # ── Embed data as JSON ────────────────────────────────────────────────────
    js_products    = json.dumps(products,    ensure_ascii=False)
    js_site_order  = json.dumps(SITE_ORDER)
    js_site_colors = json.dumps(SITE_COLORS)
    js_brands      = json.dumps(all_brands)
    js_cats        = json.dumps(all_categories)
    js_storages    = json.dumps(all_storages)

    # ── Build HTML ────────────────────────────────────────────────────────────
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>Idealz.lk — Price Intelligence</title>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
        '<style>\n'
        ':root{--bg:#080c12;--s1:#0d1219;--s2:#131a24;--s3:#1a2333;--border:#1e2d3d;'
        '--accent:#3b82f6;--green:#22c55e;--red:#ef4444;--orange:#f59e0b;--purple:#a78bfa;'
        '--text:#e2e8f0;--muted:#64748b;--dim:#334155;'
        '--fd:"Syne",sans-serif;--fb:"DM Sans",sans-serif;--fm:"DM Mono",monospace;}\n'
        '*{margin:0;padding:0;box-sizing:border-box}\n'
        'body{background:var(--bg);color:var(--text);font-family:"DM Sans",sans-serif;font-size:14px;min-height:100vh}\n'

        # topbar
        '.topbar{position:sticky;top:0;z-index:100;background:rgba(8,12,18,.95);border-bottom:1px solid var(--border);'
        'height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;backdrop-filter:blur(12px)}\n'
        '.logo{font-family:"Syne",sans-serif;font-size:17px;font-weight:800;letter-spacing:-.5px}\n'
        '.logo em{font-style:normal;color:var(--accent)}\n'
        '.tr{display:flex;align-items:center;gap:12px}\n'
        '.live{display:flex;align-items:center;gap:6px;font-family:"DM Mono",monospace;font-size:10px;'
        'color:var(--green);background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);padding:3px 10px;border-radius:20px}\n'
        '.ldot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:blink 2s ease-in-out infinite}\n'
        '@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}\n'
        '.vbadge{font-family:"DM Mono",monospace;font-size:10px;padding:3px 10px;border-radius:20px;'
        'background:rgba(59,130,246,.1);color:var(--accent);border:1px solid rgba(59,130,246,.25)}\n'
        '.datelbl{font-family:"DM Mono",monospace;font-size:10px;color:var(--muted)}\n'

        # layout
        '.layout{display:grid;grid-template-columns:250px 1fr;max-width:1600px;margin:0 auto;padding:0 20px;gap:20px}\n'

        # sidebar
        '.sidebar{padding:18px 0;position:sticky;top:62px;height:calc(100vh - 70px);overflow-y:auto;'
        'scrollbar-width:thin;scrollbar-color:var(--border) transparent}\n'
        '.sidebar::-webkit-scrollbar{width:3px}\n'
        '.sidebar::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}\n'
        '.sb-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}\n'
        '.sb-title{font-family:"Syne",sans-serif;font-size:14px;font-weight:700}\n'
        '.rst-btn{font-family:"DM Mono",monospace;font-size:10px;color:var(--muted);background:none;'
        'border:1px solid var(--border);border-radius:6px;padding:3px 9px;cursor:pointer}\n'
        '.rst-btn:hover{color:var(--text);border-color:#263545}\n'
        '.fg{margin-bottom:18px}\n'
        '.flbl{font-family:"DM Mono",monospace;font-size:10px;color:var(--muted);text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:8px;display:block}\n'

        # search
        '.sw{position:relative}\n'
        '.sw input{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:8px;'
        'color:var(--text);font-family:"DM Sans",sans-serif;font-size:13px;padding:8px 10px 8px 30px;outline:none}\n'
        '.sw input:focus{border-color:var(--accent)}\n'
        '.sw input::placeholder{color:var(--dim)}\n'
        '.sico{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--dim);font-size:13px}\n'

        # pills
        '.pw{display:flex;flex-wrap:wrap;gap:4px}\n'
        '.pill{font-family:"DM Mono",monospace;font-size:10px;padding:4px 9px;border-radius:20px;'
        'border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;'
        'transition:all .12s;white-space:nowrap;user-select:none}\n'
        '.pill:hover{border-color:var(--accent);color:var(--accent)}\n'
        '.pill.on{background:rgba(59,130,246,.14);border-color:var(--accent);color:var(--accent)}\n'

        # range + select
        '.rrow{display:flex;gap:6px;align-items:center}\n'
        '.rrow input{flex:1;min-width:0;background:var(--s2);border:1px solid var(--border);border-radius:8px;'
        'color:var(--text);font-family:"DM Mono",monospace;font-size:11px;padding:7px 8px;outline:none}\n'
        '.rrow input:focus{border-color:var(--accent)}\n'
        '.rdash{color:var(--muted)}\n'
        'select{width:100%;background:var(--s2);border:1px solid var(--border);border-radius:8px;'
        'color:var(--text);font-family:"DM Sans",sans-serif;font-size:12px;padding:8px 10px;outline:none;cursor:pointer}\n'
        '.rcnt{font-family:"DM Mono",monospace;font-size:11px;color:var(--muted);text-align:center;'
        'margin-top:8px;padding:7px;background:var(--s2);border-radius:8px;border:1px solid var(--border)}\n'
        '.rcnt strong{color:var(--accent)}\n'

        # stat cards
        '.stats{background:var(--s1);border-bottom:1px solid var(--border);padding:16px 0}\n'
        '.sg{max-width:1600px;margin:0 auto;padding:0 20px;display:grid;grid-template-columns:repeat(4,1fr);gap:10px}\n'
        '.sc{background:var(--s2);border:1px solid var(--border);border-radius:12px;padding:14px 16px;'
        'display:flex;align-items:center;gap:12px;position:relative;overflow:hidden}\n'
        '.sc::before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac)}\n'
        '.sico2{font-size:20px;color:var(--ac)}\n'
        '.sv{font-family:"Syne",sans-serif;font-size:20px;font-weight:800;color:var(--ac);letter-spacing:-1px;line-height:1}\n'
        '.sl{font-family:"DM Mono",monospace;font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:3px}\n'

        # shop chips
        '.shopbar{background:var(--s1);border-bottom:1px solid var(--border);padding:10px 0}\n'
        '.sc2{max-width:1600px;margin:0 auto;padding:0 20px;display:flex;gap:8px;flex-wrap:wrap}\n'
        '.schip{display:flex;align-items:center;gap:7px;padding:5px 12px;border-radius:8px;border:1px solid;'
        'font-family:"DM Mono",monospace;font-size:11px;cursor:pointer;background:transparent;transition:opacity .15s;white-space:nowrap}\n'
        '.schip.off{opacity:.35}\n'
        '.sdot2{width:6px;height:6px;border-radius:50%}\n'
        '.scount{color:var(--muted);font-size:10px;margin-left:2px}\n'

        # content
        '.content{padding:18px 0}\n'
        '.crow{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px}\n'

        # view toggle
        '.vt{display:flex;gap:3px;background:var(--s2);border:1px solid var(--border);border-radius:8px;padding:3px}\n'
        '.vbtn{display:flex;align-items:center;gap:5px;font-family:"DM Mono",monospace;font-size:11px;'
        'padding:5px 12px;border-radius:5px;border:none;background:transparent;color:var(--muted);cursor:pointer}\n'
        '.vbtn.on{background:var(--accent);color:#fff}\n'
        '.legend{display:flex;gap:12px}\n'
        '.leg{display:flex;align-items:center;gap:5px;font-family:"DM Mono",monospace;font-size:10px;color:var(--muted)}\n'
        '.legdot{width:7px;height:7px;border-radius:2px}\n'

        # cards
        '.cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}\n'
        '.pcard{background:var(--s1);border:1px solid var(--border);border-radius:14px;overflow:hidden;'
        'transition:border-color .2s,transform .2s}\n'
        '.pcard:hover{border-color:rgba(59,130,246,.4);transform:translateY(-2px)}\n'
        '.chdr{padding:13px 15px 9px;border-bottom:1px solid var(--s3)}\n'
        '.cbrand{font-family:"DM Mono",monospace;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:3px}\n'
        '.cname{font-size:14px;font-weight:600;line-height:1.3}\n'
        '.cmeta{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}\n'
        '.tbadge{font-family:"DM Mono",monospace;font-size:9px;padding:2px 7px;border-radius:20px;background:var(--s3);color:var(--muted);border:1px solid var(--border)}\n'
        '.sbadge{font-family:"DM Mono",monospace;font-size:9px;padding:2px 7px;border-radius:20px;'
        'background:rgba(59,130,246,.08);color:var(--accent);border:1px solid rgba(59,130,246,.25)}\n'
        '.stabs{display:flex;gap:4px;padding:9px 15px 0;flex-wrap:wrap}\n'
        '.stab{font-family:"DM Mono",monospace;font-size:10px;padding:3px 8px;border-radius:4px;'
        'border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .1s}\n'
        '.stab:hover{border-color:var(--accent);color:var(--accent)}\n'
        '.stab.on{background:rgba(59,130,246,.12);border-color:var(--accent);color:var(--accent)}\n'
        '.prows{padding:8px 15px 12px}\n'
        '.prow{display:flex;align-items:center;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--s3)}\n'
        '.prow:last-child{border-bottom:none}\n'
        '.psite{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}\n'
        '.sdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}\n'
        '.pval{font-family:"DM Mono",monospace;font-size:13px;font-weight:500}\n'
        '.pval.lo{color:var(--green)}.pval.hi{color:var(--red)}.pval.md{color:var(--text)}.pval.na{color:var(--dim);font-size:11px}\n'
        '.plink{text-decoration:none;color:inherit}\n'
        '.gapbar{margin:5px 15px 0;padding:6px 10px;background:var(--s2);border-radius:8px;'
        'display:flex;justify-content:space-between;font-family:"DM Mono",monospace;font-size:10px;color:var(--muted)}\n'
        '.gval{color:var(--orange);font-weight:500}\n'

        # table
        '.tbl-outer{overflow-x:auto;border:1px solid var(--border);border-radius:12px}\n'
        '.tbl{width:100%;border-collapse:collapse;min-width:780px}\n'
        '.tbl thead tr{background:var(--s2)}\n'
        '.tbl th{padding:9px 11px;text-align:left;font-family:"DM Mono",monospace;font-size:9px;color:var(--muted);'
        'letter-spacing:1.5px;text-transform:uppercase;border-bottom:1px solid var(--border);white-space:nowrap}\n'
        '.tbl th.r{text-align:right}\n'
        '.tbl tbody tr{border-bottom:1px solid rgba(30,45,61,.6)}\n'
        '.tbl tbody tr:hover{background:rgba(59,130,246,.03)}\n'
        '.tbl td{padding:9px 11px;font-size:12px;vertical-align:middle}\n'
        '.tnm{font-weight:500;font-size:13px}\n'
        '.tbr{font-family:"DM Mono",monospace;font-size:10px;color:var(--muted)}\n'
        '.tp{font-family:"DM Mono",monospace;font-size:12px;text-align:right;white-space:nowrap}\n'

        # loading / empty
        '.loading{display:flex;flex-direction:column;align-items:center;padding:60px 20px;gap:14px}\n'
        '.spinner{width:28px;height:28px;border:2px solid var(--border);border-top-color:var(--accent);'
        'border-radius:50%;animation:spin .7s linear infinite}\n'
        '@keyframes spin{to{transform:rotate(360deg)}}\n'
        '.empty{display:none;flex-direction:column;align-items:center;padding:60px 20px;gap:8px;color:var(--muted)}\n'
        '.eico{font-size:32px;margin-bottom:4px}\n'

        # responsive
        '@media(max-width:900px){.layout{grid-template-columns:1fr}.sidebar{position:static;height:auto}'
        '.sg{grid-template-columns:repeat(2,1fr)}}\n'
        '@media(max-width:550px){.sg{grid-template-columns:1fr 1fr}.cgrid{grid-template-columns:1fr}}\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'

        # topbar
        '<div class="topbar">\n'
        '  <div class="logo"><em>Idealz</em>.lk &mdash; Price Intelligence</div>\n'
        '  <div class="tr">\n'
        '    <div class="live"><span class="ldot"></span>LIVE</div>\n'
        '    <span class="vbadge">' + f"{total_vars:,}" + ' VARIANTS</span>\n'
        '    <span class="datelbl">' + fmt_date.upper() + '</span>\n'
        '  </div>\n'
        '</div>\n'

        # stat cards
        '<div class="stats"><div class="sg">\n'
        '  <div class="sc" style="--ac:var(--accent)">'
        '<div class="sico2">◈</div><div><div class="sv">' + f"{total_vars:,}" + '</div>'
        '<div class="sl">Total Variants</div></div></div>\n'
        '  <div class="sc" style="--ac:var(--green)">'
        '<div class="sico2">◉</div><div><div class="sv">' + f"{len(products):,}" + '</div>'
        '<div class="sl">Unique Products</div></div></div>\n'
        '  <div class="sc" style="--ac:var(--orange)">'
        '<div class="sico2">◐</div><div><div class="sv">' + f"{gap_count:,}" + '</div>'
        '<div class="sl">Price Gaps Found</div></div></div>\n'
        '  <div class="sc" style="--ac:var(--purple)">'
        '<div class="sico2">◆</div><div><div class="sv" style="font-size:16px">' + max_spread_str + '</div>'
        '<div class="sl">' + max_spread_name + '</div></div></div>\n'
        '</div></div>\n'

        # shop chips bar
        '<div class="shopbar"><div class="sc2" id="shop-chips">' + site_chips_html + '</div></div>\n'

        # main layout
        '<div class="layout">\n'

        # sidebar
        '<aside class="sidebar">\n'
        '  <div class="sb-hdr"><span class="sb-title">Filters</span>'
        '<button class="rst-btn" onclick="resetAll()">&#8635; Reset</button></div>\n'

        '  <div class="fg"><label class="flbl">Search</label>'
        '<div class="sw"><span class="sico">&#128269;</span>'
        '<input id="q" type="text" placeholder="iPhone 17, Galaxy..." oninput="go()"></div></div>\n'

        '  <div class="fg"><label class="flbl">Brand</label>'
        '<div class="pw" id="pb"></div></div>\n'

        '  <div class="fg"><label class="flbl">Category</label>'
        '<div class="pw" id="pc"></div></div>\n'

        '  <div class="fg"><label class="flbl">Storage</label>'
        '<div class="pw" id="ps"></div></div>\n'

        '  <div class="fg"><label class="flbl">Shop</label>'
        '<div class="pw" id="psh"></div></div>\n'

        '  <div class="fg"><label class="flbl">Price Range (LKR)</label>'
        '<div class="rrow">'
        '<input id="pmin" type="number" placeholder="Min" step="10000" oninput="go()">'
        '<span class="rdash">&mdash;</span>'
        '<input id="pmax" type="number" placeholder="Max" step="10000" oninput="go()">'
        '</div></div>\n'

        '  <div class="fg"><label class="flbl">Sort By</label>'
        '<select id="srt" onchange="go()">'
        '<option value="shops">Most shops first</option>'
        '<option value="price-low">Price: Low &rarr; High</option>'
        '<option value="price-high">Price: High &rarr; Low</option>'
        '<option value="spread">Biggest gap first</option>'
        '<option value="az">Name A &rarr; Z</option>'
        '</select></div>\n'

        '  <div class="rcnt">Showing <strong id="rc">0</strong> products</div>\n'
        '</aside>\n'

        # content
        '<main class="content">\n'
        '  <div class="crow">\n'
        '    <div class="vt">\n'
        '      <button class="vbtn on" id="bc" onclick="setView(\'cards\',this)">&#8862; Cards</button>\n'
        '      <button class="vbtn" id="bt" onclick="setView(\'table\',this)">&#8801; Table</button>\n'
        '    </div>\n'
        '    <div class="legend">'
        '<span class="leg"><span class="legdot" style="background:var(--green)"></span>Cheapest</span>'
        '<span class="leg"><span class="legdot" style="background:var(--red)"></span>Most expensive</span>'
        '</div>\n'
        '  </div>\n'
        '  <div class="cgrid" id="cg"></div>\n'
        '  <div class="tbl-outer" id="tv" style="display:none">'
        '<table class="tbl"><thead id="th"></thead><tbody id="tb"></tbody></table></div>\n'
        '  <div class="empty" id="emp"><div class="eico">&#8856;</div>'
        '<div>No products found</div>'
        '<button class="rst-btn" style="margin-top:10px" onclick="resetAll()">Reset filters</button></div>\n'
        '</main>\n'
        '</div>\n'

        # ── EMBEDDED JAVASCRIPT ────────────────────────────────────────────────
        '<script>\n'
        'var P=' + js_products + ';\n'
        'var SO=' + js_site_order + ';\n'
        'var SC=' + js_site_colors + ';\n'
        'var BRANDS=' + js_brands + ';\n'
        'var CATS=' + js_cats + ';\n'
        'var STORS=' + js_storages + ';\n'
        '\n'
        'var fB="all",fC="all",fS="all",fSh="all",view="cards";\n'
        '\n'
        '// ── Build filter pills on load ─────────────────────────────────────\n'
        'function buildPills(containerId, items, stateVar) {\n'
        '  var el = document.getElementById(containerId);\n'
        '  if (!el) return;\n'
        '  var html = \'<button class="pill on" onclick="setPill(\\\'\'+stateVar+\'\\\',\\\'all\\\')">All</button>\';\n'
        '  items.forEach(function(item) {\n'
        '    var safe = item.replace(/\'/g, "");\n'
        '    html += \'<button class="pill" onclick="setPill(\\\'\'+stateVar+\'\\\',\\\'\'+safe+\'\\\')">\'+ item +\'</button>\';\n'
        '  });\n'
        '  el.innerHTML = html;\n'
        '}\n'
        '\n'
        'buildPills("pb",  BRANDS, "fB");\n'
        'buildPills("pc",  CATS,   "fC");\n'
        'buildPills("ps",  STORS,  "fS");\n'
        'buildPills("psh", SO,     "fSh");\n'
        '\n'
        '// ── Set pill state ─────────────────────────────────────────────────\n'
        'function setPill(varName, val) {\n'
        '  if (varName==="fB")  fB  = val;\n'
        '  if (varName==="fC")  fC  = val;\n'
        '  if (varName==="fS")  fS  = val;\n'
        '  if (varName==="fSh") fSh = val;\n'
        '\n'
        '  // Sync shop chips bar\n'
        '  if (varName==="fSh") {\n'
        '    document.querySelectorAll(".schip").forEach(function(c){\n'
        '      var nm = c.querySelector(".scount") ? c.textContent.replace(/[0-9,]+/,"").trim() : c.textContent.trim();\n'
        '      c.classList.toggle("off", val!=="all" && nm!==val);\n'
        '    });\n'
        '  }\n'
        '\n'
        '  var ids = {fB:"pb",fC:"pc",fS:"ps",fSh:"psh"};\n'
        '  syncPills(ids[varName], val);\n'
        '  go();\n'
        '}\n'
        '\n'
        'function syncPills(id, val) {\n'
        '  document.querySelectorAll("#"+id+" .pill").forEach(function(b){\n'
        '    b.classList.toggle("on", b.textContent.trim()===(val==="all"?"All":val));\n'
        '  });\n'
        '}\n'
        '\n'
        '// Shop chip click\n'
        'function filterShop(shop) {\n'
        '  fSh = (fSh===shop) ? "all" : shop;\n'
        '  syncPills("psh", fSh);\n'
        '  document.querySelectorAll(".schip").forEach(function(c){\n'
        '    var nm = c.textContent.replace(/[\\d,]+/,"").trim();\n'
        '    c.classList.toggle("off", fSh!=="all" && nm!==fSh);\n'
        '  });\n'
        '  go();\n'
        '}\n'
        '\n'
        '// ── Reset all ──────────────────────────────────────────────────────\n'
        'function resetAll() {\n'
        '  fB=fC=fS=fSh="all";\n'
        '  document.getElementById("q").value="";\n'
        '  document.getElementById("pmin").value="";\n'
        '  document.getElementById("pmax").value="";\n'
        '  document.getElementById("srt").value="shops";\n'
        '  ["pb","pc","ps","psh"].forEach(function(id){\n'
        '    document.querySelectorAll("#"+id+" .pill").forEach(function(b,i){b.classList.toggle("on",i===0);});\n'
        '  });\n'
        '  document.querySelectorAll(".schip").forEach(function(c){c.classList.remove("off");});\n'
        '  go();\n'
        '}\n'
        '\n'
        '// ── Filter + sort ──────────────────────────────────────────────────\n'
        'function go() {\n'
        '  var q   = document.getElementById("q").value.toLowerCase().trim();\n'
        '  var mn  = parseFloat(document.getElementById("pmin").value) || 0;\n'
        '  var mx  = parseFloat(document.getElementById("pmax").value) || Infinity;\n'
        '  var srt = document.getElementById("srt").value;\n'
        '\n'
        '  var f = P.filter(function(p){\n'
        '    if (q && p.name.toLowerCase().indexOf(q)===-1) return false;\n'
        '    if (fB !=="all" && p.brand    !==fB)  return false;\n'
        '    if (fC !=="all" && p.category !==fC)  return false;\n'
        '    if (fS !=="all" && p.storage_options.indexOf(fS)===-1) return false;\n'
        '    if (fSh!=="all" && p.sites.indexOf(fSh)===-1) return false;\n'
        '    if (mn>0 || mx<Infinity) {\n'
        '      var ok=false;\n'
        '      Object.values(p.variants).forEach(function(vd){\n'
        '        Object.values(vd).forEach(function(i){if(i.price>=mn&&i.price<=mx)ok=true;});\n'
        '      });\n'
        '      if(!ok) return false;\n'
        '    }\n'
        '    return true;\n'
        '  });\n'
        '\n'
        '  f.sort(function(a,b){\n'
        '    if(srt==="price-low")  return a.market_low-b.market_low;\n'
        '    if(srt==="price-high") return b.market_low-a.market_low;\n'
        '    if(srt==="spread")     return b.spread-a.spread;\n'
        '    if(srt==="az")         return a.name.localeCompare(b.name);\n'
        '    return b.site_count-a.site_count;\n'
        '  });\n'
        '\n'
        '  document.getElementById("rc").textContent = f.length;\n'
        '  document.getElementById("emp").style.display = f.length===0 ? "flex" : "none";\n'
        '  if (view==="cards") renderCards(f);\n'
        '  else renderTable(f);\n'
        '}\n'
        '\n'
        '// ── View toggle ─────────────────────────────────────────────────────\n'
        'function setView(v, btn) {\n'
        '  view = v;\n'
        '  document.getElementById("cg").style.display = v==="cards" ? "" : "none";\n'
        '  document.getElementById("tv").style.display = v==="table" ? "" : "none";\n'
        '  document.querySelectorAll(".vbtn").forEach(function(b){b.classList.remove("on");});\n'
        '  btn.classList.add("on");\n'
        '  go();\n'
        '}\n'
        '\n'
        '// ── Build price rows HTML ────────────────────────────────────────────\n'
        'function buildRows(vdata) {\n'
        '  var prices = Object.values(vdata).map(function(i){return i.price;}).filter(Boolean);\n'
        '  var pMin = prices.length ? Math.min.apply(null,prices) : null;\n'
        '  var pMax = prices.length ? Math.max.apply(null,prices) : null;\n'
        '  return SO.map(function(site){\n'
        '    var info = vdata[site];\n'
        '    var dot  = \'<span class="sdot" style="background:\'+(SC[site]||"#555")+\'"></span>\';\n'
        '    if (!info) return \'<div class="prow"><span class="psite">\'+dot+site+\'</span><span class="pval na">&mdash;</span></div>\';\n'
        '    var cls = (info.price===pMin && prices.length>1) ? "lo" : (info.price===pMax && prices.length>1) ? "hi" : "md";\n'
        '    var str = "Rs. "+info.price.toLocaleString();\n'
        '    var val = \'<span class="pval \'+cls+\'">\'+str+\'</span>\';\n'
        '    var inner = info.url ? \'<a href="\'+info.url+\'" target="_blank" class="plink">\'+val+\'</a>\' : val;\n'
        '    return \'<div class="prow"><span class="psite">\'+dot+site+\'</span>\'+inner+\'</div>\';\n'
        '  }).join("");\n'
        '}\n'
        '\n'
        '// ── Render cards ─────────────────────────────────────────────────────\n'
        'function renderCards(f) {\n'
        '  var g = document.getElementById("cg");\n'
        '  if (f.length===0) { g.innerHTML=""; return; }\n'
        '  g.innerHTML = f.map(function(p,i){\n'
        '    var stors  = p.storage_options;\n'
        '    var defS   = (fS!=="all" && stors.indexOf(fS)!==-1) ? fS : stors[0];\n'
        '    var vdata  = (p.variants[defS]||{});\n'
        '    var tabs   = stors.length>1 ? \'<div class="stabs">\'+stors.map(function(s){\n'
        '      var nm = s.replace(/\\\\/g,"\\\\\\\\").replace(/\'/g,"\\\\\'");\n'
        '      var pnm = p.name.replace(/\\\\/g,"\\\\\\\\").replace(/\'/g,"\\\\\'");\n'
        '      return \'<button class="stab\'+(s===defS?" on":"")+\'" onclick="sw(this,\\\'\'+pnm+\'\\\',\\\'\'+nm+\'\\\')">\'+s+\'</button>\';\n'
        '    }).join("")+\'</div>\' : "";\n'
        '    var gap = p.site_count>1 ? \'<div class="gapbar"><span>Price gap</span><span class="gval">Rs. \'+p.spread.toLocaleString()+" ("+p.spread_pct+"%)</span></div>" : "";\n'
        '    return \'<div class="pcard" style="animation:none">\'+'
        '\'<div class="chdr"><div class="cbrand">\'+p.brand+\'</div><div class="cname">\'+p.name+\'</div>\'+'
        '\'<div class="cmeta"><span class="tbadge">\'+p.category+\'</span><span class="sbadge">\'+p.site_count+\' shop\'+(p.site_count!==1?"s":"")+\'</span></div></div>\'+'
        'tabs+\'<div class="prows">\'+buildRows(vdata)+\'</div>\'+gap+\'</div>\';\n'
        '  }).join("");\n'
        '}\n'
        '\n'
        '// ── Storage tab switch ───────────────────────────────────────────────\n'
        'function sw(btn, pname, stor) {\n'
        '  btn.closest(".stabs").querySelectorAll(".stab").forEach(function(b){b.classList.remove("on");});\n'
        '  btn.classList.add("on");\n'
        '  var p = P.find(function(x){return x.name===pname;});\n'
        '  if (!p) return;\n'
        '  var el = btn.closest(".pcard").querySelector(".prows");\n'
        '  if (el) el.innerHTML = buildRows(p.variants[stor]||{});\n'
        '}\n'
        '\n'
        '// ── Render table ─────────────────────────────────────────────────────\n'
        'function renderTable(f) {\n'
        '  var thead = document.getElementById("th");\n'
        '  var tbody = document.getElementById("tb");\n'
        '  thead.innerHTML = "<tr><th>Product</th><th>Brand</th><th>Storage</th>"'
        '+SO.map(function(s){return\'<th class="r" style="color:\'+(SC[s]||"#888")+\'">\'+s+"</th>";}).join("")'
        '+"<th class=\\"r\\">Gap</th></tr>";\n'
        '  if (f.length===0) { tbody.innerHTML=""; return; }\n'
        '  tbody.innerHTML = f.flatMap(function(p){\n'
        '    return p.storage_options.map(function(stor){\n'
        '      var vdata  = p.variants[stor]||{};\n'
        '      var prices = Object.values(vdata).map(function(i){return i.price;}).filter(Boolean);\n'
        '      var pMin   = prices.length?Math.min.apply(null,prices):null;\n'
        '      var pMax   = prices.length?Math.max.apply(null,prices):null;\n'
        '      var cells  = SO.map(function(site){\n'
        '        var info=vdata[site];\n'
        '        if(!info) return \'<td class="tp"><span style="color:var(--dim)">&mdash;</span></td>\';\n'
        '        var col=info.price===pMin&&prices.length>1?"var(--green)":info.price===pMax&&prices.length>1?"var(--red)":"var(--text)";\n'
        '        var val=\'<span style="color:\'+col+\'">Rs. \'+info.price.toLocaleString()+\'</span>\';\n'
        '        return \'<td class="tp">\'+(info.url?\'<a href="\'+info.url+\'" target="_blank" style="text-decoration:none">\'+val+\'</a>\':val)+\'</td>\';\n'
        '      }).join("");\n'
        '      var gap=prices.length>1?\'<span style="color:var(--orange);font-size:11px">Rs. \'+(pMax-pMin).toLocaleString()+\'</span>\':"&mdash;";\n'
        '      return \'<tr><td><div class="tnm">\'+p.name+\'</div></td><td class="tbr">\'+p.brand+\'</td><td class="tbr">\'+stor+\'</td>\'+cells+\'<td class="tp">\'+gap+\'</td></tr>\';\n'
        '    });\n'
        '  }).join("");\n'
        '}\n'
        '\n'
        '// ── Init ─────────────────────────────────────────────────────────────\n'
        'go();\n'
        '</script>\n'
        '</body>\n'
        '</html>\n'
    )

    return html


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open",     action="store_true")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    global DATA_DIR
    DATA_DIR = Path(args.data_dir)

    records, date_str = load_latest()
    products = process(records)

    print(f"\n  Processing {len(records):,} records → {len(products):,} products")

    # 1. Self-contained HTML dashboard
    html      = generate_html(records, date_str)
    html_path = DATA_DIR / f"report_{date_str}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ HTML report     : {html_path}")

    # 2. Fixed filename for GitHub Pages
    pages_path = DATA_DIR / "dashboard.html"
    with open(pages_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ GitHub Pages    : {pages_path}")

    # 3. JSON for Netlify frontend
    export_json(records, products, date_str)

    # Write REPORT_DATE to GitHub Actions env
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"REPORT_DATE={date_str}\n")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{html_path.resolve()}")

    return html_path


if __name__ == "__main__":
    main()
