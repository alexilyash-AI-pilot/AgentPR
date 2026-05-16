# AgentPR — EU Restaurant Tech News Monitor

Automatically scans ~50 European and English-language media portals **every 6 hours** for articles about AI in restaurants, Choice (your brand), and key competitors.

Results are logged to a Google Sheet and sent as Telegram notifications.  
Runs entirely on **GitHub Actions** — no server or laptop needed.

---

## What the Agent Does

Every 6 hours the agent:

1. **Fetches** articles from three sources:
   - Google News RSS (all keyword groups, EU geo-targeted)
   - NewsAPI (European + international English-language outlets)
   - Direct RSS feeds (Tier 2 & Tier 3 EU portals)

2. **Filters** — an article passes only if ALL four conditions are met:
   - **Language:** English (titles with non-Latin script are dropped)
   - **Geography:** Published by a European/EU outlet OR title explicitly mentions a European country, city, or one of your tracked companies
   - **Date:** Published on or after **1 May 2026** (articles with unknown dates are excluded)
   - **Deduplication:** URL has not been seen in any previous run

3. **Enriches** — for articles with no author in the feed, the agent scrapes the article page for a byline

4. **Logs** every new article to the **Google Sheet** (AgentPR Articles)

5. **Notifies** your Telegram group with article title, link, author, portal, country, and company matched

---

## Monitored Topics

### Your Brand
- Choice restaurant CRM / choice.app / Czech Choice restaurant

### Competitors
| Company | Keywords tracked |
|---|---|
| Sunday.app | sunday.app, sunday app |
| Deliverect | deliverect |
| Restimo | restimo |
| Restaumatic | restaumatic |
| Upmenu | upmenu |

### AI & Restaurant Tech Topics
- AI restaurant, restaurant automation, foodtech AI
- Restaurant technology startup, restaurant SaaS platform
- Restaurant digitalization, restaurant CRM, restaurant POS
- Restaurant startup funding, foodtech investment, Series A/seed

---

## Monitored Sources

### Tier 1 — European & international English-language outlets
Sifted, FT, The Guardian, Bloomberg, Reuters, Euronews, Euractiv,
Politico, The Times, The Economist, Wired, Daily Mail, Cybernews,
Pathfounders

> **US-only outlets are excluded** (TechCrunch, NYT, WSJ, Forbes, Axios, Fortune, CNBC, Business Insider, The Verge, etc.)  
> International outlets (Reuters, Bloomberg) only pass if the article title contains a European signal.

### Tier 2 — European startup & tech portals
EU-Startups, Sifted, tech.eu, Silicon Canals, The Recursive, ITKey.media,
TechFundingNews, Dispatches Europe, Maddyness, Vestbee, Startup Reporter,
Crunchbase News, The Next Web, The SaaS News, Restaurant Technology News

### Tier 3 — Regional portals
Startup Rise (UK), Forbes Hungary, Netokracija (Croatia), Bebeez (Italy),
Technews180, Start-up.ro, Friss Hírek (Hungary)

---

## EU Relevance Filter Logic

An article is considered **EU-relevant** if any of the following is true:

1. **Domain is EU-specific** — e.g., `.eu`, `sifted.eu`, `euractiv.com`, `maddyness.com`, `siliconcanals.com`, `therecursive.com`, `cybernews.com`, etc.
2. **Title mentions a European country** — France, Germany, UK, Netherlands, Poland, Czech Republic, Spain, Italy, Sweden, etc.
3. **Title mentions a European city** — London, Paris, Berlin, Amsterdam, Prague, Warsaw, Dublin, Brussels, etc.
4. **Title mentions a tracked company** — Deliverect, Restimo, Restaumatic, Upmenu, Sunday.app, Choice restaurant

---

## Google Sheet Columns

Sheet: **AgentPR Articles** → tab: `Sheet1`

| Column | Description |
|---|---|
| Article Name | Headline of the article |
| Article Link | Full URL |
| Company | Tracked company/topic matched (Choice, Deliverect, etc.) |
| Editor Name | Author first name |
| Editor Surname | Author last name |
| Editor Email | Blank (can be enriched manually or via Hunter.io) |
| Country | Country of the publication outlet |
| Portal Name | Name of the media portal |
| Date Published | When the article was published (YYYY-MM-DD) |
| Date Found | Date the agent discovered it |

---

## Telegram Notifications

Each new article triggers a message like:

```
📰 [Article title]

🔗 https://...
🏢 About: Deliverect
✍️ Editor: Jane Smith
🌐 Portal: EU Startups
🗺 Country: Europe
📅 Published: 2026-05-12
```

### Pausing / resuming Telegram

To **pause** notifications:  
→ Go to [Settings → Secrets](https://github.com/alexilyash-AI-pilot/AgentPR/settings/secrets/actions) → add secret `TELEGRAM_DISABLED` = `1`

To **resume** notifications:  
→ Delete the `TELEGRAM_DISABLED` secret

The agent continues collecting to the Google Sheet regardless.

---

## GitHub Secrets Required

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram group chat ID (e.g. `-100123456789`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full contents of the service account `.json` key file |
| `SPREADSHEET_ID` | ID from the Google Sheet URL (`/d/SPREADSHEET_ID/edit`) |
| `NEWSAPI_KEY` | Free API key from [newsapi.org](https://newsapi.org) (optional) |
| `TELEGRAM_DISABLED` | Set to `1` to pause Telegram; delete to resume |

Manage secrets: [github.com/alexilyash-AI-pilot/AgentPR/settings/secrets/actions](https://github.com/alexilyash-AI-pilot/AgentPR/settings/secrets/actions)

---

## Schedule

Runs automatically at **00:00, 06:00, 12:00, 18:00 UTC** (every 6 hours).

To trigger manually: GitHub repo → **Actions** → **AgentPR Monitor** → **Run workflow**

To change frequency, edit `.github/workflows/monitor.yml`:
```yaml
- cron: "0 */6 * * *"   # every 6 hours (current)
- cron: "0 8 * * *"      # once daily at 08:00 UTC
- cron: "0 */3 * * *"    # every 3 hours
```

---

## State Management

The agent tracks already-seen article URLs in `seen_urls.json` (committed to this repo after each run). This prevents duplicate notifications across runs.

Only articles that pass **all filters** are saved to `seen_urls.json`. URLs filtered out (old, non-EU, non-English) are re-evaluated on the next run.

---

## Adding Keywords or Portals

Edit `sources.py`:

```python
# Add a keyword
KEYWORD_GROUPS["competitors"].append("new competitor name")

# Add a domain to monitor
TIER2_DOMAINS.append("newportal.eu")

# Add country mapping for a new domain
DOMAIN_COUNTRY_MAP["newportal.eu"] = "Germany"
```

Commit and push — the next scheduled run picks up the changes automatically.

---

## Project Structure

```
AgentPR/
├── monitor.py          # Main orchestrator — fetch, filter, enrich, log, notify
├── sources.py          # Keywords, domain lists, EU signals, country mapping
├── sheets.py           # Google Sheets read/write via gspread
├── telegram_bot.py     # Telegram message formatting and sending
├── seen_urls.json      # State file — URLs already processed (auto-updated)
├── requirements.txt    # Python dependencies
└── .github/
    └── workflows/
        └── monitor.yml # GitHub Actions workflow (schedule + secrets)
```
