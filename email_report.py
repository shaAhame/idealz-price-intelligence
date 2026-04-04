"""
email_report.py — Idealz Daily Email Report Generator (v2)
============================================================
Builds a beautiful, fully working HTML email with:
  - Price changes since yesterday
  - Top competitive products table (all shops side by side)
  - Interactive filters by brand, category, storage, shop
  - Site coverage summary
  - Mobile responsive design

Recipients:
  shakeebahamed456@gmail.com
  irshadatidealz@gmail.com
  zaidh.executive@gmail.com    ← new

Outputs: data/email_report.html
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path("data")

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
    "Apple":       ["iphone", "ipad", "macbook", "airpod", "apple watch", "imac", "mac mini"],
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
    "JBL":         ["jbl"],
    "Other":       [],
}

CATEGORY_KEYWORDS = {
    "Smartphones":   ["iphone", "galaxy", "pixel", "oneplus", "xiaomi", "redmi", "oppo", "realme", "vivo", "infinix", "tecno"],
    "MacBooks":      ["macbook"],
    "iPads":         ["ipad"],
    "Smart Watches": ["watch", "band"],
    "Earbuds":       ["airpod", "buds", "earbuds"],
    "Headphones":    ["headphone", "wh-"],
    "Speakers":      ["speaker", "jbl"],
    "Laptops":       ["laptop", "notebook"],
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
    if not variant:
        return ""
    m = re.search(r"(\d+\s*(?:GB|TB))", variant, re.IGNORECASE)
    return m.group(1).replace(" ", "").upper() if m else ""


def load_latest():
    files = sorted(DATA_DIR.glob("prices_*.json"), reverse=True)
    if not files:
        print("No data files found.")
        sys.exit(1)
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    return data, files[0].stem.replace("prices_", "")


def load_yesterday(today_str):
    yesterday = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    path = DATA_DIR / f"prices_{yesterday}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lookup = {}
    for p in data:
        key = p["name"].lower().strip() + "|" + p.get("variant", "").lower().strip()
        lookup.setdefault(p["site"], {})[key] = p["price"]
    return lookup


def find_changes(products, yesterday_lookup):
    changes = []
    for p in products:
        key  = p["name"].lower().strip() + "|" + p.get("variant", "").lower().strip()
        prev = yesterday_lookup.get(p["site"], {}).get(key)
        if not prev:
            continue
        diff = prev - p["price"]
        if abs(diff) >= 2000:
            changes.append({
                "site":   p["site"],
                "name":   p["name"],
                "variant": p.get("variant", ""),
                "before": prev,
                "after":  p["price"],
                "diff":   diff,
                "pct":    round(diff / prev * 100, 1),
                "url":    p.get("url", ""),
            })
    return sorted(changes, key=lambda x: -abs(x["diff"]))


def build_products_table(products):
    """
    Groups products by name+variant, finds lowest and highest
    price per shop, returns top 30 most competitive.
    """
    by_key = defaultdict(lambda: {"sites": {}, "brand": "Other", "category": "Other"})

    for p in products:
        name    = p["name"].strip()
        variant = p.get("variant", "").strip()
        price   = p.get("price")
        site    = p.get("site", "")
        url     = p.get("url", "")

        if not name or not price or not site:
            continue

        key = name + "|||" + variant
        d   = by_key[key]
        d["name"]     = name
        d["variant"]  = variant
        d["brand"]    = detect_brand(name)
        d["category"] = detect_category(name)

        if site not in d["sites"] or price < d["sites"][site]["price"]:
            d["sites"][site] = {"price": price, "url": url}

    rows = []
    for key, d in by_key.items():
        if len(d["sites"]) < 2:
            continue
        prices = [v["price"] for v in d["sites"].values()]
        rows.append({
            "name":       d["name"],
            "variant":    d["variant"],
            "brand":      d["brand"],
            "category":   d["category"],
            "sites":      d["sites"],
            "low":        min(prices),
            "high":       max(prices),
            "spread":     max(prices) - min(prices),
            "spread_pct": round((max(prices) - min(prices)) / min(prices) * 100, 1),
        })

    rows.sort(key=lambda x: -x["spread"])
    return rows[:30]


def site_summary(products):
    counts = defaultdict(int)
    for p in products:
        counts[p["site"]] += 1
    return counts


# ── HTML PARTS ────────────────────────────────────────────────────────────────

def pill(label, fn_call, active=False):
    bg  = "#1e40af" if active else "#f1f5f9"
    col = "#ffffff"  if active else "#64748b"
    bdr = "#1e40af"  if active else "#e2e8f0"
    return (
        '<span class="fp" style="display:inline-block;margin:2px;padding:4px 11px;'
        'background:' + bg + ';color:' + col + ';border:1px solid ' + bdr + ';'
        'border-radius:20px;font-size:11px;font-family:monospace;cursor:pointer;'
        'white-space:nowrap;" onclick="' + fn_call + '">' + label + '</span>'
    )


def build_pills_group(items, fn_name):
    out = pill("All", fn_name + "('all')", active=True)
    for item in items:
        safe = item.replace("'", "")
        out += pill(item, fn_name + "('" + safe + "')")
    return out


# ── MAIN HTML BUILDER ─────────────────────────────────────────────────────────

def build_email(products, date_str):
    yesterday  = load_yesterday(date_str)
    changes    = find_changes(products, yesterday)
    top_prods  = build_products_table(products)
    counts     = site_summary(products)
    total      = len(products)
    fmt_date   = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")

    # Stats
    gap_count  = len(top_prods)
    max_gap    = max((r["spread"] for r in top_prods), default=0)
    max_gap_nm = next((r["name"][:30] for r in top_prods if r["spread"] == max_gap), "")

    # Unique filter values
    all_brands     = sorted(set(detect_brand(p["name"]) for p in products))
    all_categories = sorted(set(detect_category(p["name"]) for p in products))
    all_storages   = sorted(set(
        extract_storage(p.get("variant","")) for p in products
        if extract_storage(p.get("variant",""))
    ), key=lambda x: (
        (0 if int(re.search(r"\d+",x).group())<100 else 1) if "GB" in x else 2,
        int(re.search(r"\d+",x).group()) if re.search(r"\d+",x) else 0
    ))

    # ── Site summary pills ─────────────────────────────────────────────────────
    site_pills_html = ""
    for site in SITE_ORDER:
        c   = counts.get(site, 0)
        col = SITE_COLORS.get(site, "#64748b")
        site_pills_html += (
            '<td align="center" style="padding:6px;">'
            '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid '
            + col + ';border-radius:8px;padding:10px 14px;min-width:100px;">'
            '<div style="font-size:10px;color:' + col + ';font-weight:700;letter-spacing:.5px;'
            'text-transform:uppercase;margin-bottom:4px;">' + site + '</div>'
            '<div style="font-size:22px;font-weight:800;color:#1e293b;line-height:1;">' + str(c) + '</div>'
            '<div style="font-size:10px;color:#94a3b8;margin-top:2px;">variants</div>'
            '</div></td>'
        )

    # ── Price changes section ──────────────────────────────────────────────────
    if changes:
        rows_html = ""
        for c in changes[:20]:
            icon  = "▼" if c["diff"] > 0 else "▲"
            color = "#16a34a" if c["diff"] > 0 else "#dc2626"
            bg    = "#f0fdf4" if c["diff"] > 0 else "#fef2f2"
            nm    = c["name"][:45] + ("…" if len(c["name"]) > 45 else "")
            var   = (" · " + c["variant"]) if c["variant"] else ""
            lnk   = ('<a href="' + c["url"] + '" style="color:#0369a1;text-decoration:none;">' + nm + '</a>') if c["url"] else nm
            site_col = SITE_COLORS.get(c["site"], "#64748b")
            rows_html += (
                '<tr style="border-bottom:1px solid #f1f5f9;">'
                '<td style="padding:9px 12px;font-size:13px;">' + lnk
                + '<div style="font-size:10px;color:#94a3b8;margin-top:1px;">' + var + '</div></td>'
                '<td style="padding:9px 12px;font-size:11px;white-space:nowrap;">'
                '<span style="background:' + site_col + '20;color:' + site_col + ';padding:2px 7px;'
                'border-radius:4px;font-weight:600;">' + c["site"] + '</span></td>'
                '<td style="padding:9px 12px;font-size:12px;text-align:right;font-family:monospace;'
                'white-space:nowrap;text-decoration:line-through;color:#94a3b8;">Rs. ' + f"{c['before']:,}" + '</td>'
                '<td style="padding:9px 12px;font-size:13px;text-align:right;font-family:monospace;'
                'white-space:nowrap;font-weight:700;color:' + color + ';">Rs. ' + f"{c['after']:,}" + '</td>'
                '<td style="padding:9px 12px;text-align:right;white-space:nowrap;">'
                '<span style="background:' + bg + ';color:' + color + ';padding:3px 8px;'
                'border-radius:4px;font-size:12px;font-weight:700;font-family:monospace;">'
                + icon + ' ' + str(abs(c["pct"])) + '%</span></td>'
                '</tr>'
            )
        changes_html = (
            '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;'
            'padding:10px 16px;margin-bottom:16px;">'
            '<p style="margin:0;font-size:13px;color:#92400e;">⚠️ <strong>'
            + str(len(changes)) + ' price change' + ('s' if len(changes) != 1 else '')
            + ' detected today</strong> — review immediately.</p></div>'
            '<div style="overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;min-width:560px;">'
            '<thead><tr style="background:#f8fafc;">'
            '<th style="padding:8px 12px;text-align:left;font-size:10px;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Product</th>'
            '<th style="padding:8px 12px;text-align:left;font-size:10px;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Shop</th>'
            '<th style="padding:8px 12px;text-align:right;font-size:10px;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Before</th>'
            '<th style="padding:8px 12px;text-align:right;font-size:10px;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Now</th>'
            '<th style="padding:8px 12px;text-align:right;font-size:10px;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Change</th>'
            '</tr></thead>'
            '<tbody>' + rows_html + '</tbody></table></div>'
        )
    else:
        changes_html = (
            '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
            'padding:16px;text-align:center;">'
            '<p style="margin:0;font-size:14px;color:#166534;">'
            '✅ No significant price changes detected today (threshold: Rs. 2,000)</p></div>'
        )

    # ── Top competitive products with filters ─────────────────────────────────
    site_th = "".join(
        '<th style="padding:8px 10px;text-align:right;font-size:10px;color:'
        + SITE_COLORS.get(s, "#64748b") + ';text-transform:uppercase;letter-spacing:.5px;'
        'border-bottom:2px solid #e2e8f0;white-space:nowrap;">' + s + '</th>'
        for s in SITE_ORDER
    )

    prod_rows_html = ""
    for r in top_prods:
        cells = ""
        for site in SITE_ORDER:
            info = r["sites"].get(site)
            if info:
                p    = info["price"]
                col  = "color:#16a34a;font-weight:700;" if p == r["low"] else ("color:#dc2626;" if p == r["high"] else "")
                badge = (' <span style="background:#dcfce7;color:#15803d;font-size:9px;padding:1px 4px;border-radius:3px;">LOW</span>' if p == r["low"] else "")
                val  = "Rs. " + f"{p:,}"
                if info.get("url"):
                    val = '<a href="' + info["url"] + '" style="text-decoration:none;' + col + '">' + val + '</a>' + badge
                else:
                    val = '<span style="' + col + '">' + val + '</span>' + badge
                cells += '<td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;font-family:monospace;white-space:nowrap;">' + val + '</td>'
            else:
                cells += '<td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;color:#cbd5e1;">—</td>'

        sp_col   = "#dc2626" if r["spread_pct"] >= 15 else ("#d97706" if r["spread_pct"] >= 8 else "#64748b")
        nm       = r["name"][:45] + ("…" if len(r["name"]) > 45 else "")
        var_html = ('<div style="font-size:10px;color:#94a3b8;margin-top:1px;">' + r["variant"] + '</div>') if r["variant"] else ""
        brand_col = "#6366f1"

        prod_rows_html += (
            '<tr class="pr" data-brand="' + r["brand"] + '" data-cat="' + r["category"] + '"'
            ' data-storage="' + extract_storage(r["variant"]) + '"'
            ' data-sites="' + ",".join(r["sites"].keys()) + '"'
            ' style="border-bottom:1px solid #f1f5f9;">'
            '<td style="padding:8px 10px;font-size:13px;font-weight:500;min-width:180px;">'
            + nm + var_html + '</td>'
            '<td style="padding:8px 10px;font-size:10px;color:' + brand_col + ';font-family:monospace;white-space:nowrap;">' + r["brand"] + '</td>'
            + cells
            + '<td style="padding:8px 10px;text-align:right;white-space:nowrap;font-family:monospace;">'
            '<span style="color:' + sp_col + ';font-size:12px;font-weight:700;">Rs. ' + f"{r['spread']:,}" + '</span>'
            '<div style="font-size:10px;color:' + sp_col + ';">(' + str(r["spread_pct"]) + '%)</div>'
            '</td></tr>'
        )

    # ── Brand / Category / Storage / Shop pills ────────────────────────────────
    brand_pills    = build_pills_group(all_brands,     "filterBrand")
    cat_pills      = build_pills_group(all_categories, "filterCat")
    storage_pills  = build_pills_group(all_storages,   "filterStorage")
    shop_pills     = build_pills_group(SITE_ORDER,     "filterShop")

    # ── Assemble full email HTML ───────────────────────────────────────────────
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idealz Price Intelligence &mdash; """ + fmt_date + """</title>
<style>
  body{margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
  a{color:#0369a1;}
  .fp{cursor:pointer;user-select:none;transition:all .15s;}
  .fp:hover{opacity:.85;}
  .fp.on{background:#1e40af!important;color:#fff!important;border-color:#1e40af!important;}
  #search-box{width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;
    font-size:13px;font-family:inherit;outline:none;box-sizing:border-box;margin-bottom:10px;}
  #search-box:focus{border-color:#3b82f6;}
  #sort-sel{padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;
    font-size:12px;font-family:inherit;background:#fff;cursor:pointer;outline:none;}
  .pr{transition:background .1s;}
  .pr:hover{background:#f8fafc;}
  .pr.hidden{display:none;}
  #no-results{display:none;text-align:center;padding:30px;color:#94a3b8;font-size:13px;}
  #result-count{font-size:12px;color:#64748b;font-family:monospace;}
</style>
</head>
<body>

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:20px 12px;">
<tr><td align="center">
<table width="100%" style="max-width:820px;" cellpadding="0" cellspacing="0">

  <!-- ══ HEADER ══ -->
  <tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);border-radius:12px 12px 0 0;padding:26px 30px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="vertical-align:middle;">
        <div style="font-size:10px;color:#38bdf8;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">DAILY PRICE INTELLIGENCE REPORT</div>
        <div style="font-size:28px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;line-height:1;">Idealz.lk</div>
        <div style="font-size:13px;color:#94a3b8;margin-top:5px;">""" + fmt_date + """</div>
      </td>
      <td align="right" style="vertical-align:top;">
        <div style="background:rgba(56,189,248,.12);border:1px solid rgba(56,189,248,.25);border-radius:10px;padding:14px 20px;display:inline-block;text-align:center;">
          <div style="font-size:34px;font-weight:800;color:#38bdf8;line-height:1;">""" + f"{total:,}" + """</div>
          <div style="font-size:10px;color:#7dd3fc;letter-spacing:.5px;text-transform:uppercase;margin-top:3px;">VARIANTS TRACKED</div>
        </div>
      </td>
    </tr></table>
  </td></tr>

  <!-- ══ ALERT BANNER ══ -->
  """ + (
    '<tr><td style="background:#fffbeb;border-left:4px solid #f59e0b;padding:11px 30px;">'
    '<p style="margin:0;font-size:13px;color:#92400e;">⚠️ <strong>' + str(len(changes))
    + ' price change' + ('s' if len(changes)!=1 else '') + '</strong> detected today — review below.</p></td></tr>'
    if changes else
    '<tr><td style="background:#f0fdf4;border-left:4px solid #22c55e;padding:11px 30px;">'
    '<p style="margin:0;font-size:13px;color:#166534;">✅ No major price changes today — market is stable.</p></td></tr>'
  ) + """

  <!-- ══ STAT CARDS ══ -->
  <tr><td style="background:#ffffff;padding:20px 30px 0;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="padding:6px;width:25%;">
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px 14px;">
          <div style="font-size:10px;color:#3b82f6;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Total Variants</div>
          <div style="font-size:24px;font-weight:800;color:#1e3a8a;line-height:1;">""" + f"{total:,}" + """</div>
          <div style="font-size:10px;color:#93c5fd;margin-top:2px;">All 6 shops</div>
        </div>
      </td>
      <td style="padding:6px;width:25%;">
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 14px;">
          <div style="font-size:10px;color:#16a34a;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Price Changes</div>
          <div style="font-size:24px;font-weight:800;color:#14532d;line-height:1;">""" + str(len(changes)) + """</div>
          <div style="font-size:10px;color:#86efac;margin-top:2px;">Since yesterday</div>
        </div>
      </td>
      <td style="padding:6px;width:25%;">
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px 14px;">
          <div style="font-size:10px;color:#ea580c;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Price Gaps</div>
          <div style="font-size:24px;font-weight:800;color:#7c2d12;line-height:1;">""" + str(gap_count) + """</div>
          <div style="font-size:10px;color:#fdba74;margin-top:2px;">On 2+ shops</div>
        </div>
      </td>
      <td style="padding:6px;width:25%;">
        <div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:8px;padding:12px 14px;">
          <div style="font-size:10px;color:#9333ea;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Biggest Gap</div>
          <div style="font-size:18px;font-weight:800;color:#581c87;line-height:1.1;">Rs. """ + f"{max_gap:,}" + """</div>
          <div style="font-size:10px;color:#d8b4fe;margin-top:2px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">""" + max_gap_nm + """</div>
        </div>
      </td>
    </tr></table>
  </td></tr>

  <!-- ══ BODY ══ -->
  <tr><td style="background:#ffffff;padding:24px 30px;">

    <!-- Site coverage -->
    <h2 style="font-size:15px;font-weight:700;color:#1e293b;margin:0 0 12px;">&#128230; Products Scraped Today</h2>
    <div style="margin-bottom:24px;overflow-x:auto;">
      <table cellpadding="0" cellspacing="0"><tr>""" + site_pills_html + """</tr></table>
    </div>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 24px;">

    <!-- Price changes -->
    <h2 style="font-size:15px;font-weight:700;color:#1e293b;margin:0 0 14px;">&#9889; Price Changes Since Yesterday</h2>
    <div style="margin-bottom:28px;">""" + changes_html + """</div>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 24px;">

    <!-- Competitive products with WORKING FILTERS -->
    <h2 style="font-size:15px;font-weight:700;color:#1e293b;margin:0 0 6px;">&#127942; Top Competitive Products</h2>
    <p style="font-size:13px;color:#64748b;margin:0 0 16px;">Products listed by 2+ shops. Use the filters below to find exactly what you need. Green = market low price.</p>

    <!-- Search + Sort row -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;"><tr>
      <td style="padding-right:10px;">
        <input id="search-box" type="text" placeholder="&#128269; Search product name..." oninput="runFilters()">
      </td>
      <td style="white-space:nowrap;vertical-align:middle;">
        <select id="sort-sel" onchange="sortTable()">
          <option value="spread">Sort: Biggest Gap</option>
          <option value="low">Sort: Price Low</option>
          <option value="high">Sort: Price High</option>
          <option value="az">Sort: A &rarr; Z</option>
        </select>
      </td>
    </tr></table>

    <!-- Filter pills -->
    <div style="margin-bottom:8px;">
      <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Brand</div>
      <div id="brand-pills">""" + brand_pills + """</div>
    </div>
    <div style="margin-bottom:8px;">
      <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Category</div>
      <div id="cat-pills">""" + cat_pills + """</div>
    </div>
    <div style="margin-bottom:8px;">
      <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Storage</div>
      <div id="storage-pills">""" + storage_pills + """</div>
    </div>
    <div style="margin-bottom:14px;">
      <div style="font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Shop</div>
      <div id="shop-pills">""" + shop_pills + """</div>
    </div>

    <!-- Result count -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
      <span id="result-count">Showing """ + str(len(top_prods)) + """ products</span>
      <span style="font-size:11px;color:#94a3b8;">
        <span style="color:#16a34a;">&#9632;</span> Lowest &nbsp;
        <span style="color:#dc2626;">&#9632;</span> Highest
      </span>
    </div>

    <!-- Products table -->
    <div style="overflow-x:auto;">
    <table id="prod-table" style="width:100%;border-collapse:collapse;min-width:600px;">
      <thead>
        <tr style="background:#f8fafc;">
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Product</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Brand</th>
          """ + site_th + """
          <th style="padding:8px 10px;text-align:right;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid #e2e8f0;">Gap</th>
        </tr>
      </thead>
      <tbody id="prod-tbody">
        """ + prod_rows_html + """
        <tr id="no-results"><td colspan="10" style="padding:30px;text-align:center;color:#94a3b8;font-size:13px;">No products match your filters. <a href="#" onclick="resetAll();return false;" style="color:#3b82f6;">Reset</a></td></tr>
      </tbody>
    </table>
    </div>

  </td></tr>

  <!-- ══ FOOTER ══ -->
  <tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;border-radius:0 0 12px 12px;padding:18px 30px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:11px;color:#94a3b8;line-height:1.8;">
        &#128206; Full price list attached as CSV<br>
        &#129302; Auto-generated by Idealz Price Bot<br>
        &#128343; Scraped daily at 9:00 AM Sri Lanka Time
      </td>
      <td align="right" style="font-size:11px;color:#94a3b8;vertical-align:top;">
        <strong style="color:#1e293b;">Idealz.lk</strong><br>
        Price Intelligence System<br>
        Sri Lanka
      </td>
    </tr></table>
  </td></tr>

</table>
</td></tr>
</table>

<!-- ══ FILTER & SORT JAVASCRIPT ══ -->
<script>
// Filter state
var fBrand='all', fCat='all', fStorage='all', fShop='all';

function filterBrand(v)  { fBrand=v;   setActive('brand-pills',v);   runFilters(); }
function filterCat(v)    { fCat=v;     setActive('cat-pills',v);     runFilters(); }
function filterStorage(v){ fStorage=v; setActive('storage-pills',v); runFilters(); }
function filterShop(v)   { fShop=v;    setActive('shop-pills',v);    runFilters(); }

function setActive(containerId, val) {
  var pills = document.querySelectorAll('#'+containerId+' .fp');
  pills.forEach(function(p) {
    var matches = (val==='all' && p.textContent.trim()==='All') || p.textContent.trim()===val;
    if(matches) { p.classList.add('on'); }
    else         { p.classList.remove('on'); }
  });
}

function runFilters() {
  var q     = (document.getElementById('search-box').value||'').toLowerCase().trim();
  var rows  = document.querySelectorAll('#prod-tbody .pr');
  var shown = 0;

  rows.forEach(function(row) {
    var brand   = row.getAttribute('data-brand')   || '';
    var cat     = row.getAttribute('data-cat')     || '';
    var storage = row.getAttribute('data-storage') || '';
    var sites   = row.getAttribute('data-sites')   || '';
    var name    = row.textContent.toLowerCase();

    var ok = true;
    if(q && name.indexOf(q) === -1)             ok = false;
    if(fBrand   !=='all' && brand   !==fBrand)  ok = false;
    if(fCat     !=='all' && cat     !==fCat)    ok = false;
    if(fStorage !=='all' && storage !==fStorage) ok = false;
    if(fShop    !=='all' && sites.indexOf(fShop)===-1) ok = false;

    row.style.display = ok ? '' : 'none';
    if(ok) shown++;
  });

  var el = document.getElementById('result-count');
  if(el) el.textContent = 'Showing '+shown+' products';

  var nr = document.getElementById('no-results');
  if(nr) nr.style.display = shown===0 ? '' : 'none';
}

function sortTable() {
  var val   = document.getElementById('sort-sel').value;
  var tbody = document.getElementById('prod-tbody');
  var rows  = Array.from(tbody.querySelectorAll('.pr'));

  rows.sort(function(a,b) {
    var ga = parseFloat((a.querySelector('td:last-child span')||{}).textContent||'0'
      .replace(/[^0-9.]/g,'')) || 0;
    var gb = parseFloat((b.querySelector('td:last-child span')||{}).textContent||'0'
      .replace(/[^0-9.]/g,'')) || 0;

    if(val==='spread') return gb-ga;
    if(val==='az') {
      var na = (a.querySelector('td:first-child')||{}).textContent||'';
      var nb = (b.querySelector('td:first-child')||{}).textContent||'';
      return na.localeCompare(nb);
    }
    // For price sort — get the lowest green price in the row
    var priceA = 999999999, priceB = 999999999;
    a.querySelectorAll('td').forEach(function(td){
      var m = td.textContent.match(/[0-9,]{4,}/);
      if(m){ var n=parseInt(m[0].replace(/,/g,'')); if(n<priceA) priceA=n; }
    });
    b.querySelectorAll('td').forEach(function(td){
      var m = td.textContent.match(/[0-9,]{4,}/);
      if(m){ var n=parseInt(m[0].replace(/,/g,'')); if(n<priceB) priceB=n; }
    });
    return val==='low' ? priceA-priceB : priceB-priceA;
  });

  rows.forEach(function(r){ tbody.insertBefore(r, document.getElementById('no-results')); });
}

function resetAll() {
  fBrand=fCat=fStorage=fShop='all';
  document.getElementById('search-box').value='';
  document.getElementById('sort-sel').value='spread';
  ['brand-pills','cat-pills','storage-pills','shop-pills'].forEach(function(id){
    var pills = document.querySelectorAll('#'+id+' .fp');
    pills.forEach(function(p,i){ if(i===0) p.classList.add('on'); else p.classList.remove('on'); });
  });
  runFilters();
}
</script>

</body>
</html>"""

    return html, len(changes)


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    products, date_str = load_latest()
    html, change_count = build_email(products, date_str)

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "email_report.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Write REPORT_DATE to GitHub Actions environment
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"REPORT_DATE={date_str}\n")

    print(f"\n✓  Email report : {out_path}")
    print(f"   Products    : {len(products):,}")
    print(f"   Changes     : {change_count}")
    print(f"   Date        : {date_str}")


if __name__ == "__main__":
    main()
