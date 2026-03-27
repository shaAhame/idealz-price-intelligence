"""
email_report.py — Idealz Daily Email Report Generator
=======================================================
Reads the latest scraped data and builds a beautiful,
mobile-friendly HTML email report.

Outputs:  data/email_report.html
Sets env: REPORT_DATE  (read by GitHub Actions for email subject)
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path("data")

# ─── SITE CONFIG ──────────────────────────────────────────────────────────────

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

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def load_latest():
    files = sorted(DATA_DIR.glob("prices_*.json"), reverse=True)
    if not files:
        print("No data files found. Run scraper.py first.")
        sys.exit(1)
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    date_str = files[0].stem.replace("prices_", "")
    return data, date_str


def load_yesterday(today_str):
    yesterday = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    path = DATA_DIR / f"prices_{yesterday}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lookup = {}
    for p in data:
        lookup.setdefault(p["site"], {})[p["name"].lower().strip()] = p["price"]
    return lookup


def find_changes(today_products, yesterday_lookup):
    changes = []
    for p in today_products:
        prev = yesterday_lookup.get(p["site"], {}).get(p["name"].lower().strip())
        if not prev:
            continue
        diff = prev - p["price"]
        pct = diff / prev * 100
        if abs(diff) >= 2000:
            changes.append({
                "site": p["site"],
                "name": p["name"],
                "before": prev,
                "after": p["price"],
                "diff": diff,
                "pct": round(pct, 1),
                "url": p.get("url", ""),
            })
    return sorted(changes, key=lambda x: -abs(x["diff"]))


def build_top_products(products):
    """Products listed on 2+ sites — the most competitively priced ones."""
    by_name = defaultdict(dict)
    for p in products:
        name = p["name"].strip()
        site = p["site"]
        if site not in by_name[name] or p["price"] < by_name[name][site]["price"]:
            by_name[name][site] = {"price": p["price"], "url": p.get("url", "")}

    rows = []
    for name, sites in by_name.items():
        if len(sites) < 2:
            continue
        prices = [v["price"] for v in sites.values()]
        rows.append({
            "name": name,
            "sites": sites,
            "low": min(prices),
            "high": max(prices),
            "spread": max(prices) - min(prices),
            "spread_pct": round((max(prices) - min(prices)) / min(prices) * 100, 1),
        })

    rows.sort(key=lambda x: -x["spread"])
    return rows[:25]  # top 25 most price-competitive products


def site_summary(products):
    counts = defaultdict(int)
    for p in products:
        counts[p["site"]] += 1
    return counts


# ─── HTML BUILDER ─────────────────────────────────────────────────────────────

def build_email(products, date_str):
    yesterday = load_yesterday(date_str)
    changes   = find_changes(products, yesterday)
    top_prods = build_top_products(products)
    counts    = site_summary(products)
    total     = len(products)
    fmt_date  = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")

    # ── Price change rows ──────────────────────────────────────────
    if changes:
        change_rows = ""
        for c in changes[:15]:
            icon  = "▼" if c["diff"] > 0 else "▲"
            color = "#16a34a" if c["diff"] > 0 else "#dc2626"
            bg    = "#f0fdf4" if c["diff"] > 0 else "#fef2f2"
            name  = c["name"][:55] + "…" if len(c["name"]) > 55 else c["name"]
            link  = f'<a href="{c["url"]}" style="color:#0369a1;text-decoration:none;">{name}</a>' if c["url"] else name
            change_rows += f"""
            <tr>
              <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;">{link}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:12px;color:#64748b;white-space:nowrap;">{c['site']}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;text-align:right;font-family:monospace;white-space:nowrap;text-decoration:line-through;color:#94a3b8;">Rs. {c['before']:,}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:13px;text-align:right;font-family:monospace;white-space:nowrap;font-weight:600;color:{color};">Rs. {c['after']:,}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;white-space:nowrap;">
                <span style="background:{bg};color:{color};padding:2px 7px;border-radius:4px;font-weight:600;font-family:monospace;">{icon} {abs(c['pct'])}%</span>
              </td>
            </tr>"""
        changes_section = f"""
        <h2 style="font-size:16px;font-weight:700;color:#1e293b;margin:0 0 14px;">⚡ Price Changes Since Yesterday</h2>
        <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
          <thead>
            <tr style="background:#f8fafc;">
              <th style="padding:9px 14px;text-align:left;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Product</th>
              <th style="padding:9px 14px;text-align:left;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Site</th>
              <th style="padding:9px 14px;text-align:right;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Before</th>
              <th style="padding:9px 14px;text-align:right;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Now</th>
              <th style="padding:9px 14px;text-align:right;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Change</th>
            </tr>
          </thead>
          <tbody>{change_rows}</tbody>
        </table>
        </div>"""
    else:
        changes_section = """
        <h2 style="font-size:16px;font-weight:700;color:#1e293b;margin:0 0 14px;">⚡ Price Changes Since Yesterday</h2>
        <p style="color:#64748b;font-size:14px;padding:20px;background:#f8fafc;border-radius:8px;text-align:center;margin:0;">
          ✅ No significant price changes detected today (threshold: Rs. 2,000)
        </p>"""

    # ── Competitive products table ─────────────────────────────────
    prod_rows = ""
    for row in top_prods:
        cells = ""
        for site in SITE_ORDER:
            info = row["sites"].get(site)
            if info:
                p     = info["price"]
                url   = info.get("url", "")
                color = ""
                badge = ""
                if p == row["low"]:
                    color = "color:#16a34a;font-weight:700;"
                    badge = ' <span style="background:#dcfce7;color:#15803d;font-size:9px;padding:1px 4px;border-radius:3px;font-weight:600;">LOW</span>'
                elif p == row["high"]:
                    color = "color:#dc2626;"

                val = f"Rs. {p:,}"
                if url:
                    val = f'<a href="{url}" style="text-decoration:none;{color}">{val}</a>'
                else:
                    val = f'<span style="{color}">{val}</span>'
                cells += f'<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;font-family:monospace;white-space:nowrap;">{val}{badge}</td>'
            else:
                cells += '<td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;color:#cbd5e1;">—</td>'

        spread_color = "#dc2626" if row["spread_pct"] >= 15 else "#d97706" if row["spread_pct"] >= 8 else "#64748b"
        name = row["name"][:50] + "…" if len(row["name"]) > 50 else row["name"]
        prod_rows += f"""
        <tr>
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:500;min-width:180px;">{name}</td>
          {cells}
          <td style="padding:9px 10px;border-bottom:1px solid #f1f5f9;font-size:11px;text-align:right;white-space:nowrap;color:{spread_color};font-weight:600;font-family:monospace;">Rs. {row['spread']:,}<br><span style="font-size:10px;font-weight:400;">({row['spread_pct']}%)</span></td>
        </tr>"""

    site_header_cells = "".join(
        f'<th style="padding:9px 10px;text-align:right;font-size:10px;color:{SITE_COLORS.get(s,"#64748b")};letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;white-space:nowrap;">{s}</th>'
        for s in SITE_ORDER
    )

    # ── Site summary pills ─────────────────────────────────────────
    site_pills = ""
    for site in SITE_ORDER:
        count = counts.get(site, 0)
        color = SITE_COLORS.get(site, "#64748b")
        site_pills += f"""
        <div style="display:inline-block;margin:4px;padding:8px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;border-top:3px solid {color};">
          <div style="font-size:11px;color:{color};font-weight:700;letter-spacing:.5px;text-transform:uppercase;">{site}</div>
          <div style="font-size:22px;font-weight:800;color:#1e293b;line-height:1.1;">{count}</div>
          <div style="font-size:10px;color:#94a3b8;">products</div>
        </div>"""

    # ── Assemble full email ────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idealz Price Intelligence — {fmt_date}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;">
<tr><td align="center">
<table width="100%" style="max-width:780px;" cellpadding="0" cellspacing="0">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);border-radius:12px 12px 0 0;padding:28px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <div style="font-size:11px;color:#38bdf8;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">DAILY PRICE INTELLIGENCE REPORT</div>
          <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">Idealz.lk</div>
          <div style="font-size:14px;color:#94a3b8;margin-top:4px;">{fmt_date}</div>
        </td>
        <td align="right" style="vertical-align:top;">
          <div style="background:rgba(56,189,248,0.15);border:1px solid rgba(56,189,248,0.3);border-radius:8px;padding:12px 18px;display:inline-block;">
            <div style="font-size:32px;font-weight:800;color:#38bdf8;line-height:1;">{total:,}</div>
            <div style="font-size:11px;color:#7dd3fc;letter-spacing:.5px;text-transform:uppercase;">products tracked</div>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- Alert banner (only if changes found) -->
  {'<tr><td style="background:#fef3c7;border-left:4px solid #f59e0b;padding:12px 32px;"><p style="margin:0;font-size:13px;color:#92400e;">⚠️ <strong>' + str(len(changes)) + ' price change' + ('s' if len(changes)!=1 else '') + '</strong> detected today — review the table below immediately.</p></td></tr>' if changes else '<tr><td style="background:#f0fdf4;border-left:4px solid #22c55e;padding:12px 32px;"><p style="margin:0;font-size:13px;color:#166534;">✅ No major price changes today — market is stable.</p></td></tr>'}

  <!-- Body -->
  <tr><td style="background:#ffffff;padding:28px 32px;">

    <!-- Site summary -->
    <h2 style="font-size:16px;font-weight:700;color:#1e293b;margin:0 0 14px;">📦 Products Scraped Today</h2>
    <div style="margin-bottom:28px;">{site_pills}</div>

    <!-- Divider -->
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 28px;">

    <!-- Price changes section -->
    <div style="margin-bottom:32px;">{changes_section}</div>

    <!-- Divider -->
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 28px;">

    <!-- Competitive products -->
    <h2 style="font-size:16px;font-weight:700;color:#1e293b;margin:0 0 6px;">🏆 Top 25 Most Competitive Products</h2>
    <p style="font-size:13px;color:#64748b;margin:0 0 16px;">Products listed by 2+ competitors — shows where price gaps are largest. Green = market low, Red = market high.</p>
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-width:600px;">
      <thead>
        <tr style="background:#f8fafc;">
          <th style="padding:9px 10px;text-align:left;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Product</th>
          {site_header_cells}
          <th style="padding:9px 10px;text-align:right;font-size:11px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;">Price Gap</th>
        </tr>
      </thead>
      <tbody>{prod_rows}</tbody>
    </table>
    </div>

  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;border-radius:0 0 12px 12px;padding:20px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="font-size:11px;color:#94a3b8;line-height:1.6;">
          📎 Full price list attached as CSV<br>
          🤖 Auto-generated by Idealz Price Intelligence Bot<br>
          🕗 Scraped daily at 8:00 AM Sri Lanka Time
        </td>
        <td align="right" style="font-size:11px;color:#94a3b8;vertical-align:top;">
          Idealz.lk<br>
          Sri Lanka
        </td>
      </tr>
    </table>
  </td></tr>

</table>
</td></tr>
</table>

</body>
</html>"""

    return html, len(changes)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    products, date_str = load_latest()
    html, change_count = build_email(products, date_str)

    out_path = DATA_DIR / "email_report.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Write REPORT_DATE to GitHub Actions environment
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"REPORT_DATE={date_str}\n")

    print(f"✓ Email report saved: {out_path}")
    print(f"  Products: {len(products)}  |  Changes: {change_count}  |  Date: {date_str}")
