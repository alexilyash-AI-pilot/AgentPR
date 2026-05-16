# AgentPR — Restaurant Tech News Monitor

Automatically scans ~60 European and global media portals every 6 hours for articles about AI in restaurants, your brand (Choice), and competitors (Deliverect, Sunday.app, Restimo, Restaumatic, Upmenu, and more).

- New articles are logged to a Google Sheet
- Telegram notifications are sent to your group with article link, author, and portal
- Runs entirely on GitHub Actions — no server or laptop needed

---

## Setup (one-time, ~20 minutes)

### Step 1 — Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts (give it a name like "AgentPR Bot")
3. Copy the **Bot Token** (looks like `7123456789:AAFxxxxxx`)
4. Add your bot to the Telegram group where you want notifications
5. Send any message in the group, then open this URL in your browser (replace TOKEN):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
6. Find `"chat":{"id":` in the response — that number is your **Chat ID** (may be negative for groups, e.g. `-1001234567890`)

---

### Step 2 — Create a Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank spreadsheet
2. Name it **AgentPR Articles**
3. Copy the **Spreadsheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   ```
   (the long string between `/d/` and `/edit`)

---

### Step 3 — Set up Google Cloud Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable **Google Sheets API** and **Google Drive API**:
   - APIs & Services → Enable APIs → search "Google Sheets API" → Enable
   - Repeat for "Google Drive API"
4. Create a Service Account:
   - IAM & Admin → Service Accounts → Create Service Account
   - Name: `agentpr-bot`, click Create
   - Skip role assignment, click Done
5. Create a JSON key:
   - Click the service account → Keys tab → Add Key → Create new key → JSON
   - Download the `.json` file — keep it safe, never commit it to git
6. Share your Google Sheet with the service account email:
   - Open your spreadsheet → Share → paste the service account email (ends in `@...iam.gserviceaccount.com`) → Editor role

---

### Step 4 — Get a NewsAPI Key (free)

1. Go to [newsapi.org](https://newsapi.org) and sign up
2. Copy your **API Key** from the dashboard

---

### Step 5 — Push to GitHub

```bash
cd /Users/alex/Desktop/AgentPR
git add .
git commit -m "Initial AgentPR setup"
# Create a new repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/agentpr.git
git push -u origin main
```

---

### Step 6 — Add GitHub Actions Secrets

In your GitHub repository go to **Settings → Secrets and variables → Actions → New repository secret** and add these 5 secrets:

| Secret Name                    | Value                                          |
|-------------------------------|------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`           | Your bot token from BotFather                  |
| `TELEGRAM_CHAT_ID`             | Your group chat ID (e.g. `-1001234567890`)     |
| `GOOGLE_SERVICE_ACCOUNT_JSON`  | Paste the **entire contents** of the JSON file |
| `SPREADSHEET_ID`               | The ID from your Google Sheet URL              |
| `NEWSAPI_KEY`                  | Your NewsAPI key                               |

---

### Step 7 — Run Manually to Test

Go to your GitHub repo → **Actions** tab → **AgentPR Monitor** → **Run workflow**

Check:
- GitHub Actions logs for errors
- Your Telegram group for test notifications
- Your Google Sheet for new rows

---

## Schedule

The agent runs automatically every 6 hours (00:00, 06:00, 12:00, 18:00 UTC).

To change frequency, edit `.github/workflows/monitor.yml`:
```yaml
- cron: "0 */6 * * *"   # every 6 hours
- cron: "0 8 * * *"      # once daily at 08:00 UTC
- cron: "0 */3 * * *"    # every 3 hours
```

---

## What Gets Monitored

**Your brand:** Choice restaurant CRM, choice.app

**Competitors:** Sunday.app, Deliverect, Restimo, Restaumatic, Upmenu

**Topics:** AI restaurant, restaurant technology, foodtech, restaurant SaaS, restaurant automation, restaurant digitalization

**Sources (~60 portals):**
- Major international: TechCrunch, Forbes, Bloomberg, Reuters, FT, Guardian, Wired, CNBC, Politico, The Verge, Axios, and more
- European startup: EU-Startups, Sifted, tech.eu, Silicon Canals, The Recursive, ITKey.media, TechFundingNews, Dispatches Europe, and more
- Regional: forbes.hu, netokracija.com, start-up.ro, startuprise.co.uk, bebeez.eu, and more

---

## Google Sheet Columns

| Column         | Description                              |
|---------------|------------------------------------------|
| Article Name   | Headline of the article                  |
| Article Link   | Full URL                                 |
| Company        | Which tracked company it's about         |
| Editor Name    | Author first name (scraped from byline)  |
| Editor Surname | Author last name                         |
| Editor Email   | Left blank (can add Hunter.io later)     |
| Country        | Country of the publication               |
| Portal Name    | Name of the media outlet                 |
| Date Published | When the article was published           |
| Date Found     | When the agent found it                  |

---

## Adding More Keywords or Portals

Edit `sources.py`:
- Add keywords to `KEYWORD_GROUPS`
- Add domains to `TIER1_DOMAINS`, `TIER2_DOMAINS`, or `TIER3_DOMAINS`
- Add country mappings to `DOMAIN_COUNTRY_MAP`

Commit and push — the next run picks up the changes automatically.
