# AgentPR

Automated PR and media monitoring system for [ChoiceQR](https://choiceqr.com), a European restaurant QR-ordering software company. Tracks competitor and industry news across ~80 sources, stores results in Google Sheets, and delivers summaries via Telegram.

---

## Architecture

The system has two independent parts:

| Part | Runtime | Entry point |
|------|---------|-------------|
| **Daily Monitor** | GitHub Actions (cron) | `monitor.py` |
| **Interactive Bot** | Railway (always-on) | `bot_server.py` |

```
┌─────────────────────────────────────────────────────┐
│                  Daily Monitor                       │
│  GitHub Actions · 09:00 CET · monitor.py            │
│                                                      │
│  RSS feeds / media outlets                          │
│       ↓                                              │
│  Fetch & parse articles                             │
│       ↓                                              │
│  Filter pipeline (date → EU → subject → dedup)      │
│       ↓                          ↓                   │
│  Google Sheet            Telegram group              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                 Interactive Bot                      │
│  Railway · @ChoicePRbot · bot_server.py             │
│                                                      │
│  Telegram message                                   │
│       ↓                                              │
│  FastAPI webhook → OpenAI GPT-4o-mini (tool calls)  │
│       ↓                                              │
│  search_articles / send_to_group / create_sheet_tab  │
└─────────────────────────────────────────────────────┘
```

---

## Monitored Companies

19 companies are tracked (competitors and industry players):

| # | Company |
|---|---------|
| 1 | Deliverect |
| 2 | Sunday |
| 3 | Flipdish |
| 4 | StoreKit |
| 5 | UpMenu |
| 6 | Restimo |
| 7 | Restaumatic |
| 8 | TheFork |
| 9 | OpenTable |
| 10 | Quandoo |
| 11 | Tableo |
| 12 | ResDiary |
| 13 | Zenchef |
| 14 | Eat App |
| 15 | SevenRooms |
| 16 | Otter |
| 17 | TableQR |
| 18 | MENU TIGER |
| 19 | ChoiceQR |

All company names and associated keywords are defined in `sources.py`.

---

## Sources

Approximately 80 sources are queried each run:

- **Google News RSS** — geo-targeted EU feeds per company
- **~25 major media outlets** — TechCrunch, Bloomberg, Reuters, Forbes, and similar
- **~15 startup/tech ecosystem portals** — tech.eu, sifted.eu, eu-startups.com, and similar
- **Direct RSS from regional EU portals**

All source URLs and domain tier classifications are defined in `sources.py`.

---

## Filtering Pipeline

Articles pass through a strict relevance policy before being saved:

1. **Date cutoff** — Only articles published on or after January 1, 2026 are kept.

2. **EU relevance** — Article must satisfy at least one of:
   - Domain has an EU country-code TLD (`.de`, `.fr`, `.nl`, etc.)
   - Domain is classified as TIER1 or TIER2 in `sources.py`
   - Article body contains an EU-related keyword

3. **Tracked-company match** — The article title or summary must explicitly mention at least one of the 19 monitored companies. Generic `Restaurant Tech` matches and query-only matches are rejected.

4. **Company-news relevance** — The tracked company must be the subject of the article or part of a meaningful business/product update, such as funding, investment, acquisitions, partnerships, integrations, launches, AI, POS integrations, QR ordering updates, reservations platform updates, delivery management updates, loyalty/CRM, market expansion, enterprise deals, executive hires, or strategic changes.

5. **Consumer restaurant noise rejection** — Restaurant openings, food-writer recommendations, dining guides, food weeks, local venue lists, menu announcements, set/seasonal/tasting/holiday menus, restaurant-week deals, Super Bowl deals, open-hours stories, best/top restaurant lists, Michelin guides, restaurant reviews, hotel/spa/Disney/venue reopenings, and chef/venue-specific stories are rejected even when they contain broad restaurant keywords. Confirmed rejected examples include "White Tiger" restaurant openings, "Indian regional flavours", "Liverpool food and drink writer", "favourite venues", "new city centre restaurant", "mum's cooking", "Mile High Asian Food Week", "where to dine", and "food week".

6. **Cross-run deduplication** — Checks the Google Sheet master database:
   - Exact URL match → skip
   - Title similarity > 85% (fuzzy) → skip

7. **Within-run story dedup** — Among articles collected in the same run covering the same story (title similarity > 70%), only the highest-tier source is kept.

---

## Google Sheet Schema

Master database: [`1nSkFz_2kUs76LIO_mcl5x0WvhuESyRWJ4bSigOoO5UM`](https://docs.google.com/spreadsheets/d/1nSkFz_2kUs76LIO_mcl5x0WvhuESyRWJ4bSigOoO5UM)

| Column | Description |
|--------|-------------|
| Date Added | When the row was written to the sheet |
| Publication Date | Article publish date from the RSS feed |
| Article Title | Full article headline |
| Company Mentions | Which tracked companies appear in the article |
| Short Summary | Auto-generated one-line summary |
| Portal Name | Name of the publishing outlet |
| Article URL | Canonical article URL |
| Status | `Sent` or `Not Sent` (Telegram delivery status) |
| First Detected Time | Timestamp of first detection across all runs |

Sheet integration is handled by `sheets.py`.

---

## Telegram Format

Notifications are sent to group `-1003524787352` by `@AiPRChoice`.

Each message contains:
- Company name
- Article title
- Short summary
- Portal name
- Article link
- Publication date
- Link to the Google Sheet

Errors and pipeline failures are also sent as Telegram alerts to the same group.

Message formatting logic lives in `telegram_bot.py`.

---

## Interactive Bot

**Bot**: `@ChoicePRbot`  
**URL**: `https://agentpr-production.up.railway.app`  
**Stack**: FastAPI + uvicorn, OpenAI GPT-4o-mini, Python

### How it works

1. User sends a natural-language message to `@ChoicePRbot` in Telegram.
2. The Railway server receives the webhook and routes it to the FastAPI handler.
3. The handler passes the message to GPT-4o-mini with tool-calling enabled.
4. The model calls one or more tools to fulfill the request.
5. Results are returned to the user in Telegram.

### Available tools

| Tool | Description |
|------|-------------|
| `search_articles` | Full-text search across the Google Sheet database |
| `send_to_group` | Sends formatted results to the Telegram group |
| `create_sheet_tab` | Creates a new tab in the Google Sheet with query results |

### Bot behavior

- **Company aliases**: Understands shorthand — "Choice" → ChoiceQR, "Sunday" → Sunday.app, etc.
- **Multi-query**: Runs 2–3 query variations per request for better recall.
- **Deduplication**: Deduplicates results across query variations before presenting them.
- **Confirmation step**: Asks where to send results (Telegram group or new Sheet tab) before acting.
- **Conversation memory**: Per-chat message history is maintained for contextual follow-ups.
- **Concurrency lock**: Per-chat threading lock prevents concurrent request corruption.

Implementation: `bot_server.py` (webhook server) and `tools.py` (tool functions).

---

## Setup & Secrets

### Required GitHub Actions secrets

| Secret | Value / Description |
|--------|---------------------|
| `TELEGRAM_BOT_TOKEN` | Bot token for `@AiPRChoice` |
| `TELEGRAM_CHAT_ID` | `-1003524787352` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON of the Google service account credentials |
| `SPREADSHEET_ID` | `1nSkFz_2kUs76LIO_mcl5x0WvhuESyRWJ4bSigOoO5UM` |

### Railway environment variables

The same secrets above are required as environment variables on the Railway service, plus any additional variables needed by `bot_server.py` (e.g. `OPENAI_API_KEY`).

### Schedule

The daily monitor runs via `.github/workflows/monitor.yml` at **07:00 UTC (09:00 CET)** every day.

---

## File Reference

| File | Purpose |
|------|---------|
| `monitor.py` | Main orchestrator for daily GitHub Actions runs |
| `sources.py` | Company list, keywords, source URLs, domain tier classifications |
| `sheets.py` | Google Sheets read/write integration |
| `telegram_bot.py` | Telegram message formatting and delivery |
| `tools.py` | Bot tool implementations (`search_articles`, `send_to_group`, `create_sheet_tab`) |
| `bot_server.py` | FastAPI webhook server for the interactive bot |
| `bot_handler.py` | Telegram update handler logic |
| `Dockerfile` | Container image for Railway deployment |
| `railway.json` | Railway service configuration |
| `requirements.txt` | Python dependencies |
| `.github/workflows/monitor.yml` | GitHub Actions cron schedule |
