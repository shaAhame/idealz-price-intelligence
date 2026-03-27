"""
dashboard.py — Reads scraped data, builds CEO HTML dashboard.
Output: data/report_YYYY-MM-DD.html
"""

import json, sys, os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

SITE_ORDER = ["Celltronics","ONEi","Present Solution","Life Mobile","LuxuryX","Genius Mobile"]
SITE_COLORS = {
    "Celltronics":"#0ea5e9","ONEi":"#8b5cf6","Present Solution":"#10b981",
    "Life Mobile":"#f59e0b","LuxuryX":"#eab308","Genius Mobile":"#ec4899",
}

def load_latest():
    files = sorted(DATA_DIR.glob("prices_*.json"), reverse=True)
    if not files:
        print("No data files found."); sys.exit(1)
    with open(files[0], encoding="utf-8") as f:
        data = json.load(f)
    return data, files[0].stem.replace("prices_","")

def build_comparison(products):
    by_name = defaultdict(dict)
    for p in products:
        name, site, price = p["name"].strip(), p["site"], p["price"]
        if site not in by_name[name] or price < by_name[name][site]["price"]:
            by_name[name][site] = {"price": price, "url": p.get("url","")}
    rows = []
    for name, site_prices in by_name.items():
        prices = [v["price"] for v in site_prices.values()]
        rows.append({"name":name,"sites":site_prices,"market_low":min(prices),"market_high":max(prices),"site_count":len(site_prices)})
    rows.sort(key=lambda x: (-x["site_count"], x["name"].lower()))
    return rows

def generate_html(rows, date_str, total):
    by_site = defaultdict(int)
    for row in rows:
        for site in row["sites"]: by_site[site] += 1

    table_rows = ""
    for row in rows:
        cells = ""
        for site in SITE_ORDER:
            info = row["sites"].get(site)
            if info:
                p, url = info["price"], info.get("url","")
                style = ""
                badge = ""
                if p == row["market_low"] and row["site_count"] > 1:
                    style = "color:#16a34a;font-weight:600;"
                    badge = '<span style="background:#dcfce7;color:#15803d;font-size:9px;padding:1px 5px;border-radius:3px;margin-left:3px;">LOW</span>'
                elif p == row["market_high"] and row["site_count"] > 1:
                    style = "color:#dc2626;"
                val = f"Rs. {p:,}"
                if url: val = f'<a href="{url}" target="_blank" style="text-decoration:none;{style}">{val}</a>'
                else: val = f'<span style="{style}">{val}</span>'
                cells += f'<td style="padding:9px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;white-space:nowrap;font-family:monospace;">{val}{badge}</td>'
            else:
                cells += '<td style="padding:9px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;text-align:right;color:#cbd5e1;">—</td>'
        spread = ""
        if row["site_count"] > 1:
            diff = row["market_high"] - row["market_low"]
            pct  = round(diff/row["market_low"]*100, 1)
            spread = f'<span style="font-family:monospace;font-size:11px;color:#64748b;">Rs. {diff:,} ({pct}%)</span>'
        table_rows += f'<tr><td style="padding:9px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;font-weight:500;">{row["name"][:60]}</td>{cells}<td style="padding:9px 12px;border-bottom:1px solid #f1f5f9;text-align:right;">{spread}</td></tr>'

    sum_pills = "".join(
        f'<div style="display:inline-block;margin:4px;padding:10px 16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;border-top:3px solid {SITE_COLORS.get(s,"#64748b")};">'
        f'<div style="font-size:10px;color:{SITE_COLORS.get(s,"#64748b")};font-weight:700;text-transform:uppercase;letter-spacing:.5px;">{s}</div>'
        f'<div style="font-size:24px;font-weight:800;color:#1e293b;">{by_site.get(s,0)}</div>'
        f'<div style="font-size:10px;color:#94a3b8;">products</div></div>'
        for s in SITE_ORDER
    )
    hdr_cells = "".join(
        f'<th style="padding:9px 12px;text-align:right;font-size:10px;color:{SITE_COLORS.get(s,"#64748b")};letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;white-space:nowrap;">{s}</th>'
        for s in SITE_ORDER
    )
    fmt = datetime.strptime(date_str,"%Y-%m-%d").strftime("%B %d, %Y")

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Idealz Price Dashboard — {fmt}</title>
<style>
body{{margin:0;padding:20px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
.card{{background:#fff;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
h1{{margin:0 0 4px;font-size:24px;color:#1e293b}}
h2{{margin:0 0 16px;font-size:16px;color:#1e293b}}
input[type=text]{{padding:9px 14px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;width:300px;outline:none}}
select{{padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none}}
table{{width:100%;border-collapse:collapse}}
thead tr{{background:#f8fafc}}
th{{padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.5px;text-transform:uppercase;border-bottom:2px solid #e2e8f0;white-space:nowrap}}
</style></head><body>
<div class="card"><div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
<div><div style="font-size:11px;color:#0ea5e9;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px;">COMPETITOR PRICE DATABASE</div>
<h1>Idealz.lk</h1><p style="margin:4px 0 0;color:#64748b;font-size:14px;">{fmt} · {total:,} products tracked</p></div>
<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px 18px;text-align:center;">
<div style="font-size:28px;font-weight:800;color:#1d4ed8;">{len(rows)}</div>
<div style="font-size:11px;color:#3b82f6;">unique products</div></div></div></div>
<div class="card"><h2>Products Scraped Per Site</h2><div>{sum_pills}</div></div>
<div class="card">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
<input type="text" placeholder="Search product…" oninput="search(this.value)" id="q">
<select onchange="filterSites(this.value)">
<option value="all">All products</option><option value="2">On 2+ sites</option><option value="3">On 3+ sites</option></select>
<select onchange="sortRows(this.value)">
<option value="sites">Most competitive</option><option value="name">Name A→Z</option><option value="spread">Biggest gap</option></select>
<span id="cnt" style="margin-left:auto;font-size:12px;color:#64748b;">{len(rows)} products</span></div>
<div style="overflow-x:auto;"><table id="t">
<thead><tr><th>Product</th>{hdr_cells}<th style="text-align:right;border-bottom:2px solid #e2e8f0;">Price gap</th></tr></thead>
<tbody id="tb">{table_rows}</tbody></table></div></div>
<script>
const all=[...document.querySelectorAll('#tb tr')];
let mf='all',sq='';
function applyFilters(){{all.forEach(r=>{{const n=(r.cells[0]?.innerText||'').toLowerCase();const c=[...r.querySelectorAll('td')].filter(td=>td.innerText.trim()&&td.innerText.trim()!=='—').length-2;const ms=mf==='all'?true:mf==='2'?c>=2:c>=3;r.style.display=ms&&n.includes(sq)?'':'none'}});document.getElementById('cnt').textContent=all.filter(r=>r.style.display!=='none').length+' products'}}
function search(v){{sq=v.toLowerCase();applyFilters()}}
function filterSites(v){{mf=v;applyFilters()}}
function sortRows(v){{const tb=document.getElementById('tb');const rows=[...all];rows.sort((a,b)=>{{if(v==='name')return a.cells[0].innerText.localeCompare(b.cells[0].innerText);if(v==='sites'){{const ca=[...a.querySelectorAll('td')].filter(t=>t.innerText.trim()&&t.innerText!=='—').length;const cb=[...b.querySelectorAll('td')].filter(t=>t.innerText.trim()&&t.innerText!=='—').length;return cb-ca}}if(v==='spread'){{const g=r=>{{const t=r.cells[r.cells.length-1]?.innerText||'';const m=t.match(/[\d,]+/);return m?-parseInt(m[0].replace(',','')):0}};return g(a)-g(b)}}return 0}});rows.forEach(r=>tb.appendChild(r));applyFilters()}}
</script></body></html>"""

if __name__ == "__main__":
    products, date_str = load_latest()
    rows = build_comparison(products)
    html = generate_html(rows, date_str, len(products))
    out = DATA_DIR / f"report_{date_str}.html"
    with open(out,"w",encoding="utf-8") as f: f.write(html)
    env = os.environ.get("GITHUB_ENV")
    if env:
        with open(env,"a") as f: f.write(f"REPORT_DATE={date_str}\n")
    print(f"✓ Dashboard: {out}  ({len(products)} products, {len(rows)} unique)")
