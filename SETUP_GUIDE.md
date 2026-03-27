# Idealz.lk Price Intelligence — GitHub Setup Guide

## What happens every day at 8:00 AM Sri Lanka Time

1. GitHub runs the scraper automatically (no computer needed)
2. All 6 competitor sites are scraped
3. An HTML dashboard is built
4. A **price report email** is sent to:
   - shakeebahamed456@gmail.com
   - irshadatidealz@gmail.com
5. A CSV attachment of all prices is included
6. All data is saved in the repo for 30-day history

---

## ONE-TIME SETUP (takes about 15 minutes)

### Step 1 — Create a GitHub account
Go to https://github.com and sign up (free).

### Step 2 — Create a new repository
1. Click the **+** button (top right) → **New repository**
2. Name it: `idealz-price-intelligence`
3. Set to **Private** (so competitors can't see it)
4. Click **Create repository**

### Step 3 — Upload these files
In your new repository, click **uploading an existing file** and upload all files from this folder:
```
scraper.py
dashboard.py
email_report.py
requirements.txt
.gitignore
.github/workflows/daily_scrape.yml    ← this must go inside .github/workflows/
```

To create the folder structure for the workflow file:
1. Click **Add file** → **Create new file**
2. In the filename box, type: `.github/workflows/daily_scrape.yml`
3. Paste the contents of `daily_scrape.yml`
4. Click **Commit new file**

### Step 4 — Create a Gmail App Password (for sending emails)

⚠️ You CANNOT use your normal Gmail password. You need an App Password.

1. Go to your Google Account: https://myaccount.google.com
2. Click **Security** in the left menu
3. Under "How you sign in to Google", click **2-Step Verification**
   - If not enabled, enable it first (required)
4. Scroll to the bottom → click **App passwords**
5. Choose:
   - App: **Mail**
   - Device: **Other** → type "Idealz Bot"
6. Click **Generate**
7. **Copy the 16-character password shown** (you'll need it in Step 5)

> Use whichever Gmail you want to send FROM.
> We recommend creating a dedicated account like `idealpricingbot@gmail.com`

### Step 5 — Add secrets to GitHub

Secrets keep your password safe — GitHub encrypts them and they're never visible.

1. In your repository, click **Settings** (top menu)
2. Click **Secrets and variables** → **Actions** (left sidebar)
3. Click **New repository secret** and add these TWO secrets:

| Secret Name | Value |
|-------------|-------|
| `MAIL_USERNAME` | The Gmail address you're sending FROM (e.g. `idealpricingbot@gmail.com`) |
| `MAIL_PASSWORD` | The 16-character App Password from Step 4 |

### Step 6 — Test it manually

1. In your repository, click **Actions** (top menu)
2. Click **Idealz Daily Price Intelligence** (left sidebar)
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch it run — takes about 20-30 minutes
5. Check both email inboxes for the report!

---

## What the email looks like

**Subject:** `📊 Idealz Price Intelligence — March 27, 2026`

**Email contains:**
- Total products tracked today
- ⚡ Price changes since yesterday (highlighted in green/red)
- 🏆 Top 25 most competitive products across all 6 sites
- Market lowest price highlighted in green
- Market highest price in red
- Price gap (spread) between competitors

**Attachment:** `prices_2026-03-27.csv` — full price list, opens in Excel

---

## Schedule

The scraper runs automatically at **8:00 AM Sri Lanka Time** every day.

To change the time, edit `.github/workflows/daily_scrape.yml`:
```yaml
- cron: '30 2 * * *'   # 02:30 UTC = 08:00 AM SL
```

UTC to Sri Lanka conversion: Sri Lanka is UTC+5:30
- 8:00 AM SL  = 02:30 UTC
- 9:00 AM SL  = 03:30 UTC
- 10:00 AM SL = 04:30 UTC

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Email not received | Check spam folder. Verify MAIL_USERNAME and MAIL_PASSWORD secrets are correct. |
| Workflow fails | Click the failed run in Actions → read the error log |
| "Invalid credentials" | Regenerate the Gmail App Password (Step 4) |
| 0 products scraped | A competitor site may be down. Check their site manually. |
| GitHub Actions disabled | Go to Settings → Actions → Allow all actions |

---

## View past reports

All reports are saved in the repository under the `data/` folder:
- `data/prices_YYYY-MM-DD.json` — raw data
- `data/prices_YYYY-MM-DD.csv` — Excel spreadsheet  
- `data/report_YYYY-MM-DD.html` — CEO dashboard (download and open in browser)
- `data/alerts_YYYY-MM-DD.json` — price changes detected

You can also download any run's artifacts from **Actions** → click any run → **Artifacts** section at the bottom.

---

*Idealz.lk Price Intelligence System · Automated via GitHub Actions*
