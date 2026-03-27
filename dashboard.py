"""
dashboard.py — Idealz.lk CEO Price Intelligence Dashboard (v4)
================================================================
Reads the latest scraped JSON data and generates a rich HTML dashboard with:

  Tab 1 — Brand Summary     : All brands × all shops, lowest price per variant
  Tab 2 — Shop Comparison   : Side-by-side price table per shop
  Tab 3 — Price Gap Finder  : Products where competitors vary most in price
  Tab 4 — Full Price List   : Every product + every variant, searchable + filterable

Usage:
  python dashboard.py           # generates from latest data file
  python dashboard.py --open    # auto-opens in browser after generating
"""

import json
import os
import sys
import argparse
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ── BRAND DETECTION ───────────────────────────────────────────────────────────

BRAND_KEYWORDS = {
    "Apple":        ["iphone", "ipad", "macbook", "airpod", "apple watch", "imac", "mac mini", "mac studio"],
    "Samsung":      ["samsung", "galaxy"],
    "Google":       ["google pixel", "pixel"],
    "Sony":         ["sony"],
    "OnePlus":      ["oneplus", "one plus"],
    "Xiaomi":       ["xiaomi", "redmi", "poco"],
    "Oppo":         ["oppo"],
    "Realme":       ["realme"],
    "Vivo":         ["vivo"],
    "Infinix":      ["infinix"],
    "Tecno":        ["tecno"],
    "Honor":        ["honor"],
    "Nokia":        ["nokia"],
    "Nothing":      ["nothing", "cmf"],
    "JBL":          ["jbl"],
    "Marshall":     ["marshall"],
    "Anker":        ["anker", "soundcore"],
    "Bose":         ["bose"],
    "DJI":          ["dji", "osmo", "insta360"],
    "PlayStation":  ["playstation", "ps5", "ps4"],
    "Dyson":        ["dyson"],
    "Other":        [],
}

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
    "LuxuryX":          "#eab308",
    "Genius Mobile":    "#ec4899",
}


def detect_brand(name):
    name_lower = name.lower()
    for brand, keywords in BRAND_KEYWORDS.items():
        if brand == "Other":
            continue
        for kw in keywords:
            if kw in name_lower:
                return brand
    return "Other"


def fmt_price(p):
    if p is None:
        return "—"
    return f"Rs. {p:,}"


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

def process_data(records):
    """
    Builds 3 data structures from raw records:

    1. brand_data:  { brand: { site: { "product_name variant": price } } }
    2. product_data: { "name|variant": { site: price, url, brand } }
    3. site_counts:  { site: count }
    """
    brand_data   = defaultdict(lambda: defaultdict(dict))
    product_data = defaultdict(lambda: {"sites": {}, "brand": "Other", "name": "", "variant": ""})
    site_counts  = defaultdict(int)

    for r in records:
        name    = r.get("name", "").strip()
        variant = r.get("variant", "").strip()
        price   = r.get("price")
        site    = r.get("site", "")
        url     = r.get("url", "")

        if not name or not price or not site:
            continue

        brand = detect_brand(name)
        key   = f"{name}|||{variant}"

        # brand_data
        label = f"{name} {variant}".strip()
        existing = brand_data[brand][site].get(label)
        if existing is None or price < existing:
            brand_data[brand][site][label] = price

        # product_data
        pd = product_data[key]
        pd["name"]    = name
        pd["variant"] = variant
        pd["brand"]   = brand
        if site not in pd["sites"] or price < pd["sites"][site]["price"]:
            pd["sites"][site] = {"price": price, "url": url}

        site_counts[site] += 1

    return brand_data, product_data, site_counts


def build_brand_summary(brand_data):
    """
    For each brand → for each product variant → lowest price per site.
    Returns list of rows sorted by brand then product name.
    """
    rows = []
    for brand in sorted(brand_data.keys()):
        # Collect all product labels across all sites for this brand
        all_labels = set()
        for site_products in brand_data[brand].values():
            all_labels.update(site_products.keys())

        for label in sorted(all_labels):
            prices = {}
            for site in SITE_ORDER:
                p = brand_data[brand].get(site, {}).get(label)
                if p:
                    prices[site] = p

            if not prices:
                continue

            vals        = list(prices.values())
            market_low  = min(vals)
            market_high = max(vals)
            spread      = market_high - market_low
            spread_pct  = round(spread / market_low * 100, 1) if market_low else 0

            rows.append({
                "brand":       brand,
                "label":       label,
                "prices":      prices,
                "market_low":  market_low,
                "market_high": market_high,
                "spread":      spread,
                "spread_pct":  spread_pct,
                "site_count":  len(prices),
            })

    return rows


def build_price_gaps(brand_summary):
    """Top products sorted by price spread — biggest opportunities."""
    multi = [r for r in brand_summary if r["site_count"] >= 2]
    return sorted(multi, key=lambda x: -x["spread"])[:50]


# ── HTML GENERATOR ────────────────────────────────────────────────────────────

def generate_html(records, date_str):
    brand_data, product_data, site_counts = process_data(records)
    brand_summary = build_brand_summary(brand_data)
    price_gaps    = build_price_gaps(brand_summary)

    total      = len(records)
    fmt_date   = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    all_brands = sorted(set(r["brand"] for r in brand_summary))

    # ── Tab 1: Brand Summary table rows ──────────────────────────────────────
    brand_rows_html = ""
    current_brand   = None
    for row in brand_summary:
        # Brand header row
        if row["brand"] != current_brand:
            current_brand = row["brand"]
            count = sum(1 for r in brand_summary if r["brand"] == current_brand)
            brand_rows_html += f"""
            <tr class="brand-header-row" data-brand="{current_brand}">
              <td colspan="9" style="padding:10px 14px 6px;font-size:12px;font-weight:700;
                color:#1e293b;background:#f1f5f9;border-top:2px solid #e2e8f0;
                letter-spacing:.5px;text-transform:uppercase;">
                {current_brand} <span style="font-weight:400;color:#94a3b8;font-size:11px;margin-left:6px;">{count} products</span>
              </td>
            </tr>"""

        # Price cells
        cells = ""
        for site in SITE_ORDER:
            p = row["prices"].get(site)
            if p:
                style = ""
                badge = ""
                if p == row["market_low"] and row["site_count"] > 1:
                    style = "color:#16a34a;font-weight:700;"
                    badge = '<span style="font-size:9px;background:#dcfce7;color:#15803d;padding:1px 4px;border-radius:3px;margin-left:3px;">LOW</span>'
                elif p == row["market_high"] and row["site_count"] > 1:
                    style = "color:#dc2626;"
                    badge = '<span style="font-size:9px;background:#fee2e2;color:#dc2626;padding:1px 4px;border-radius:3px;margin-left:3px;">HIGH</span>'
                cells += f'<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:monospace;font-size:12px;white-space:nowrap;"><span style="{style}">Rs. {p:,}</span>{badge}</td>'
            else:
                cells += '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;text-align:right;color:#cbd5e1;font-size:12px;">—</td>'

        spread_html = ""
        if row["site_count"] > 1:
            sc = "#dc2626" if row["spread_pct"] >= 15 else "#d97706" if row["spread_pct"] >= 8 else "#64748b"
            spread_html = f'<span style="font-family:monospace;font-size:11px;color:{sc};">Rs. {row["spread"]:,}<br><span style="font-size:10px;">({row["spread_pct"]}%)</span></span>'

        brand_rows_html += f"""
        <tr class="product-row" data-brand="{row['brand']}" data-label="{row['label'].lower()}" data-sites="{row['site_count']}">
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:500;min-width:220px;">{row['label'][:65]}</td>
          {cells}
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;text-align:right;">{spread_html}</td>
        </tr>"""

    # ── Tab 2: Shop-wise summary (each shop as a column, brand as rows) ───────
    shop_brand_html = ""
    for brand in all_brands:
        brand_rows = [r for r in brand_summary if r["brand"] == brand]
        if not brand_rows:
            continue

        # For each site: count products and show price range
        site_cells = ""
        for site in SITE_ORDER:
            site_prices = [r["prices"][site] for r in brand_rows if site in r["prices"]]
            if site_prices:
                lo = min(site_prices)
                hi = max(site_prices)
                cnt = len(site_prices)
                color = SITE_COLORS.get(site, "#64748b")
                if lo == hi:
                    price_display = f'Rs. {lo:,}'
                else:
                    price_display = f'Rs. {lo:,}<br><span style="font-size:10px;color:#94a3b8;">to Rs. {hi:,}</span>'
                site_cells += f'''<td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:center;font-size:12px;font-family:monospace;vertical-align:middle;">
                  <div style="font-weight:600;color:#1e293b;">{price_display}</div>
                  <div style="font-size:10px;color:{color};margin-top:3px;">{cnt} variant{"s" if cnt!=1 else ""}</div>
                </td>'''
            else:
                site_cells += '<td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;text-align:center;color:#e2e8f0;font-size:12px;">—</td>'

        shop_brand_html += f"""
        <tr class="shop-row" data-brand="{brand}">
          <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:600;color:#1e293b;white-space:nowrap;">{brand}</td>
          {site_cells}
        </tr>"""

    # ── Tab 3: Price Gap rows ─────────────────────────────────────────────────
    gap_rows_html = ""
    for i, row in enumerate(price_gaps, 1):
        cells = ""
        for site in SITE_ORDER:
            p = row["prices"].get(site)
            if p:
                style = ""
                if p == row["market_low"]:
                    style = "color:#16a34a;font-weight:700;"
                elif p == row["market_high"]:
                    style = "color:#dc2626;"
                cells += f'<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:monospace;font-size:12px;white-space:nowrap;"><span style="{style}">Rs. {p:,}</span></td>'
            else:
                cells += '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;text-align:right;color:#cbd5e1;font-size:12px;">—</td>'

        pct = row["spread_pct"]
        bar_color = "#dc2626" if pct >= 20 else "#d97706" if pct >= 10 else "#64748b"
        bar_width = min(100, int(pct * 3))

        gap_rows_html += f"""
        <tr class="gap-row" data-brand="{row['brand']}">
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:11px;font-weight:600;color:#94a3b8;text-align:center;">{i}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:12px;font-weight:600;color:{bar_color};white-space:nowrap;">
            Rs. {row['spread']:,}<br>
            <div style="height:4px;background:#f1f5f9;border-radius:2px;margin-top:3px;width:80px;">
              <div style="height:4px;background:{bar_color};border-radius:2px;width:{bar_width}%;"></div>
            </div>
          </td>
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:11px;color:{bar_color};font-weight:700;">{pct}%</td>
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:500;">{row['label'][:60]}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:11px;color:#64748b;font-family:monospace;">{row['brand']}</td>
          {cells}
        </tr>"""

    # ── Tab 4: Full price list ─────────────────────────────────────────────────
    full_rows_html = ""
    for row in brand_summary:
        cells = ""
        for site in SITE_ORDER:
            p = row["prices"].get(site)
            if p:
                style = ""
                if p == row["market_low"] and row["site_count"] > 1:
                    style = "color:#16a34a;font-weight:700;"
                elif p == row["market_high"] and row["site_count"] > 1:
                    style = "color:#dc2626;"
                cells += f'<td style="padding:8px 10px;border-bottom:1px solid #f8fafc;text-align:right;font-family:monospace;font-size:12px;white-space:nowrap;"><span style="{style}">Rs. {p:,}</span></td>'
            else:
                cells += '<td style="padding:8px 10px;border-bottom:1px solid #f8fafc;text-align:right;color:#e2e8f0;font-size:11px;">—</td>'

        full_rows_html += f"""
        <tr class="full-row" data-brand="{row['brand']}" data-label="{row['label'].lower()}">
          <td style="padding:8px 10px;border-bottom:1px solid #f8fafc;font-size:11px;color:#94a3b8;white-space:nowrap;">{row['brand']}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:500;">{row['label'][:70]}</td>
          {cells}
        </tr>"""

    # ── Site header cells ──────────────────────────────────────────────────────
    site_headers = "".join(
        f'<th style="padding:10px 10px;text-align:right;font-size:10px;color:{SITE_COLORS.get(s,"#64748b")};'
        f'letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;white-space:nowrap;">{s}</th>'
        for s in SITE_ORDER
    )

    # ── Brand filter pills ─────────────────────────────────────────────────────
    brand_pills = '<button onclick="filterBrand(\'all\',this)" class="bpill active">All</button>'
    for brand in all_brands:
        brand_pills += f'<button onclick="filterBrand(\'{brand}\',this)" class="bpill">{brand}</button>'

    # ── Site count summary pills ───────────────────────────────────────────────
    site_pills = ""
    for site in SITE_ORDER:
        count = site_counts.get(site, 0)
        color = SITE_COLORS.get(site, "#64748b")
        site_pills += f'''<div style="display:inline-block;margin:4px;padding:10px 16px;
          background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;border-top:3px solid {color};">
          <div style="font-size:10px;color:{color};font-weight:700;text-transform:uppercase;letter-spacing:.5px;">{site}</div>
          <div style="font-size:22px;font-weight:800;color:#1e293b;line-height:1.1;">{count}</div>
          <div style="font-size:10px;color:#94a3b8;">variants tracked</div>
        </div>'''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idealz.lk — Price Intelligence Dashboard {fmt_date}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1e293b;min-height:100vh}}

/* ── TOP BAR ── */
.topbar{{background:linear-gradient(135deg,#0f172a,#1e3a5f);padding:18px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
.logo{{font-size:20px;font-weight:800;color:#fff;letter-spacing:-0.5px}}
.logo span{{color:#38bdf8}}
.topbar-meta{{display:flex;align-items:center;gap:16px}}
.badge{{font-size:11px;padding:4px 12px;border-radius:20px;font-weight:600;letter-spacing:.5px}}
.badge-blue{{background:rgba(56,189,248,.15);color:#38bdf8;border:1px solid rgba(56,189,248,.3)}}
.badge-green{{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.25)}}
.date-lbl{{font-size:11px;color:#94a3b8;font-family:monospace}}

/* ── WRAP ── */
.wrap{{max-width:1700px;margin:0 auto;padding:24px 20px}}

/* ── TABS ── */
.tabs{{display:flex;gap:2px;background:#e2e8f0;border-radius:10px;padding:4px;margin-bottom:24px;width:fit-content}}
.tab{{font-size:13px;font-weight:600;padding:8px 20px;border:none;background:none;color:#64748b;cursor:pointer;border-radius:7px;transition:all .15s;white-space:nowrap}}
.tab.active{{background:#fff;color:#1e293b;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.tab:hover:not(.active){{color:#1e293b}}
.tab-panel{{display:none}}
.tab-panel.active{{display:block}}

/* ── CARDS ── */
.card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}

/* ── CONTROLS ── */
.controls{{display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap}}
.search-box{{display:flex;align-items:center;gap:8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:0 12px}}
.search-box input{{background:none;border:none;outline:none;color:#1e293b;font-size:13px;padding:9px 0;width:260px}}
.search-box input::placeholder{{color:#94a3b8}}
select{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;color:#1e293b;font-size:13px;padding:8px 12px;outline:none;cursor:pointer}}
.cnt{{margin-left:auto;font-size:12px;color:#94a3b8;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:6px 12px}}
.cnt span{{color:#0ea5e9;font-weight:600}}

/* ── BRAND PILLS ── */
.bpill{{font-size:12px;font-weight:600;padding:5px 14px;border:1px solid #e2e8f0;border-radius:20px;background:#f8fafc;color:#64748b;cursor:pointer;transition:all .15s;white-space:nowrap}}
.bpill:hover,.bpill.active{{background:#0ea5e9;color:#fff;border-color:#0ea5e9}}
.brand-pills{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}}

/* ── TABLES ── */
.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #e2e8f0}}
table{{width:100%;border-collapse:collapse;font-size:13px;min-width:900px}}
thead tr{{background:#f8fafc}}
th{{padding:10px 10px;text-align:left;font-size:10px;color:#94a3b8;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;white-space:nowrap}}
tbody tr:hover{{background:#f8fafc}}
.brand-header-row td{{cursor:pointer}}

/* ── SECTION TITLES ── */
.sec-title{{font-size:18px;font-weight:700;color:#1e293b;margin-bottom:4px}}
.sec-sub{{font-size:13px;color:#64748b;margin-bottom:16px}}

/* ── STAT CARDS ── */
.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.stat-card{{background:#fff;border-radius:10px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.stat-lbl{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
.stat-val{{font-size:30px;font-weight:800;color:#0ea5e9;letter-spacing:-1px;line-height:1}}
.stat-desc{{font-size:12px;color:#64748b;margin-top:4px}}

@media(max-width:900px){{.stat-grid{{grid-template-columns:repeat(2,1fr)}}.wrap{{padding:12px 10px}}}}
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <div class="logo"><span>Idealz</span>.lk — Price Intelligence</div>
  <div class="topbar-meta">
    <span class="badge badge-green">LIVE DATA</span>
    <span class="badge badge-blue">{total:,} VARIANTS TRACKED</span>
    <span class="date-lbl">{fmt_date.upper()}</span>
  </div>
</div>

<div class="wrap">

  <!-- STAT CARDS -->
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-lbl">Total Variants</div>
      <div class="stat-val">{total:,}</div>
      <div class="stat-desc">Across all 6 competitors</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">Brands Tracked</div>
      <div class="stat-val">{len(all_brands)}</div>
      <div class="stat-desc">Auto-detected from product names</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">Price Gap Opportunities</div>
      <div class="stat-val">{len(price_gaps)}</div>
      <div class="stat-desc">Products listed by 2+ competitors</div>
    </div>
    <div class="stat-card">
      <div class="stat-lbl">Biggest Price Gap</div>
      <div class="stat-val" style="font-size:22px;">{"Rs. " + f"{price_gaps[0]['spread']:,}" if price_gaps else "—"}</div>
      <div class="stat-desc">{price_gaps[0]['label'][:40] if price_gaps else "—"}</div>
    </div>
  </div>

  <!-- SITE SUMMARY -->
  <div class="card" style="margin-bottom:20px;">
    <div class="sec-title">Products Tracked Per Shop</div>
    <div style="margin-top:10px;">{site_pills}</div>
  </div>

  <!-- TABS -->
  <div class="tabs">
    <button class="tab active" onclick="showTab('brand',this)">📱 By Brand</button>
    <button class="tab" onclick="showTab('shop',this)">🏪 By Shop</button>
    <button class="tab" onclick="showTab('gap',this)">⚡ Price Gaps</button>
    <button class="tab" onclick="showTab('full',this)">📋 Full List</button>
  </div>

  <!-- ══ TAB 1: BY BRAND ══ -->
  <div id="tab-brand" class="tab-panel active">
    <div class="card">
      <div class="sec-title">Brand × Shop Price Summary</div>
      <div class="sec-sub">Every product variant grouped by brand. Green = market lowest price. Red = market highest. Spread = price gap between cheapest and most expensive shop.</div>

      <div class="brand-pills" id="brand-pills-1">{brand_pills}</div>

      <div class="controls">
        <div class="search-box">
          <span style="color:#94a3b8;font-size:14px;">🔍</span>
          <input type="text" placeholder="Search product..." oninput="searchBrand(this.value)" id="brand-search">
        </div>
        <select onchange="filterBrandSites(this.value,'brand')">
          <option value="all">All products</option>
          <option value="2">On 2+ shops</option>
          <option value="3">On 3+ shops</option>
        </select>
        <select onchange="sortBrand(this.value)">
          <option value="default">Default order</option>
          <option value="low">Price low → high</option>
          <option value="spread">Biggest gap first</option>
          <option value="az">Name A → Z</option>
        </select>
        <div class="cnt">Showing <span id="brand-cnt">{len(brand_summary)}</span> products</div>
      </div>

      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th style="min-width:220px;">Product / Variant</th>
              {site_headers}
              <th style="text-align:right;border-bottom:2px solid #e2e8f0;">Price Spread</th>
            </tr>
          </thead>
          <tbody id="brand-tbody">{brand_rows_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ══ TAB 2: BY SHOP ══ -->
  <div id="tab-shop" class="tab-panel">
    <div class="card">
      <div class="sec-title">Shop × Brand Comparison</div>
      <div class="sec-sub">For each brand, see which shops carry it and their price range (lowest → highest variant price). Helps decide where each brand is cheapest.</div>

      <div class="brand-pills" id="brand-pills-2">{brand_pills}</div>

      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th style="min-width:120px;">Brand</th>
              {site_headers}
            </tr>
          </thead>
          <tbody id="shop-tbody">{shop_brand_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ══ TAB 3: PRICE GAPS ══ -->
  <div id="tab-gap" class="tab-panel">
    <div class="card">
      <div class="sec-title">⚡ Biggest Price Gaps — CEO Action List</div>
      <div class="sec-sub">Products where competitors differ most in price. These are your biggest opportunities — price Idealz just below the green (market low) to win customers.</div>

      <div class="brand-pills" id="brand-pills-3">{brand_pills}</div>

      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:40px;">#</th>
              <th>Gap (LKR)</th>
              <th>Gap %</th>
              <th style="min-width:200px;">Product</th>
              <th>Brand</th>
              {site_headers}
            </tr>
          </thead>
          <tbody id="gap-tbody">{gap_rows_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ══ TAB 4: FULL LIST ══ -->
  <div id="tab-full" class="tab-panel">
    <div class="card">
      <div class="sec-title">Full Price List — All Variants</div>
      <div class="sec-sub">Every product, every storage/colour variant, every shop. Search or filter by brand below.</div>

      <div class="brand-pills" id="brand-pills-4">{brand_pills}</div>

      <div class="controls">
        <div class="search-box">
          <span style="color:#94a3b8;font-size:14px;">🔍</span>
          <input type="text" placeholder="Search product or variant..." oninput="searchFull(this.value)" id="full-search">
        </div>
        <div class="cnt">Showing <span id="full-cnt">{len(brand_summary)}</span> rows</div>
      </div>

      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th>Brand</th>
              <th style="min-width:240px;">Product / Variant</th>
              {site_headers}
            </tr>
          </thead>
          <tbody id="full-tbody">{full_rows_html}</tbody>
        </table>
      </div>
    </div>
  </div>

</div><!-- /wrap -->

<script>
// ── TAB SWITCHING ─────────────────────────────────────────────────────────────
function showTab(id, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}}

// ── BRAND FILTER ──────────────────────────────────────────────────────────────
let activeBrand = 'all';

function filterBrand(brand, btn) {{
  activeBrand = brand;
  // Update all brand pill groups
  document.querySelectorAll('.bpill').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.bpill').forEach(b => {{
    if (b.textContent.trim() === (brand === 'all' ? 'All' : brand)) b.classList.add('active');
  }});
  applyBrandFilter();
  applyShopFilter();
  applyGapFilter();
  applyFullFilter();
}}

function applyBrandFilter() {{
  const rows = document.querySelectorAll('#brand-tbody .product-row');
  const headers = document.querySelectorAll('#brand-tbody .brand-header-row');
  const search = document.getElementById('brand-search')?.value.toLowerCase() || '';
  let vis = 0;
  rows.forEach(r => {{
    const bMatch = activeBrand === 'all' || r.dataset.brand === activeBrand;
    const sMatch = !search || r.dataset.label.includes(search);
    r.style.display = bMatch && sMatch ? '' : 'none';
    if (bMatch && sMatch) vis++;
  }});
  headers.forEach(h => {{
    const bMatch = activeBrand === 'all' || h.dataset.brand === activeBrand;
    h.style.display = bMatch ? '' : 'none';
  }});
  const el = document.getElementById('brand-cnt');
  if (el) el.textContent = vis;
}}

function applyShopFilter() {{
  document.querySelectorAll('#shop-tbody .shop-row').forEach(r => {{
    r.style.display = activeBrand === 'all' || r.dataset.brand === activeBrand ? '' : 'none';
  }});
}}

function applyGapFilter() {{
  document.querySelectorAll('#gap-tbody .gap-row').forEach(r => {{
    r.style.display = activeBrand === 'all' || r.dataset.brand === activeBrand ? '' : 'none';
  }});
}}

function applyFullFilter() {{
  const search = document.getElementById('full-search')?.value.toLowerCase() || '';
  let vis = 0;
  document.querySelectorAll('#full-tbody .full-row').forEach(r => {{
    const bMatch = activeBrand === 'all' || r.dataset.brand === activeBrand;
    const sMatch = !search || r.dataset.label.includes(search);
    r.style.display = bMatch && sMatch ? '' : 'none';
    if (bMatch && sMatch) vis++;
  }});
  const el = document.getElementById('full-cnt');
  if (el) el.textContent = vis;
}}

// ── SEARCH ────────────────────────────────────────────────────────────────────
function searchBrand(q) {{ applyBrandFilter(); }}
function searchFull(q)  {{ applyFullFilter(); }}

// ── FILTER BY NUMBER OF SITES ─────────────────────────────────────────────────
function filterBrandSites(val, tab) {{
  document.querySelectorAll('#brand-tbody .product-row').forEach(r => {{
    const sites = parseInt(r.dataset.sites || '1');
    const ok = val === 'all' || sites >= parseInt(val);
    r.style.display = ok ? '' : 'none';
  }});
  applyBrandFilter();
}}

// ── SORT ──────────────────────────────────────────────────────────────────────
function sortBrand(val) {{
  const tbody = document.getElementById('brand-tbody');
  const rows  = [...tbody.querySelectorAll('.product-row')];
  rows.sort((a, b) => {{
    if (val === 'az') return a.dataset.label.localeCompare(b.dataset.label);
    if (val === 'low') {{
      const getMin = el => {{
        const prices = [...el.querySelectorAll('td')].map(td => {{
          const m = td.textContent.match(/[\d,]{{5,}}/);
          return m ? parseInt(m[0].replace(/,/g,'')) : Infinity;
        }});
        return Math.min(...prices.filter(p => p < Infinity));
      }};
      return getMin(a) - getMin(b);
    }}
    if (val === 'spread') {{
      const getSpread = el => {{
        const last = el.cells[el.cells.length - 1]?.textContent || '';
        const m = last.match(/[\d,]{{4,}}/);
        return m ? -parseInt(m[0].replace(/,/g,'')) : 0;
      }};
      return getSpread(a) - getSpread(b);
    }}
    return 0;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""

    return html


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="Open in browser after generating")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    global DATA_DIR
    DATA_DIR = Path(args.data_dir)

    records, date_str = load_latest()
    html = generate_html(records, date_str)

    out_path = DATA_DIR / f"report_{date_str}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Write REPORT_DATE to GitHub Actions environment
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"REPORT_DATE={date_str}\n")

    print(f"\n✓ Dashboard saved: {out_path}")
    print(f"  Records: {len(records)}  |  Date: {date_str}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{out_path.resolve()}")

    return out_path


if __name__ == "__main__":
    main()
