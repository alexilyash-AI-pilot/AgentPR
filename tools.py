"""
AgentPR Tool implementations — called by Claude via the Anthropic tools API.

Tools:
  search_articles(query, days)   → EU/English filtered Google News RSS results
  send_to_group()                → post cached articles to Telegram group
  create_sheet_tab()             → new worksheet tab in AgentPR Articles sheet

Results are cached server-side by chat_id so send_to_group / create_sheet_tab
don't need to receive article data as parameters.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 10

# ---------------------------------------------------------------------------
# EU / language filters (mirrors monitor.py)
# ---------------------------------------------------------------------------

US_ONLY_DOMAINS = {
    "techcrunch.com", "washingtonpost.com", "nytimes.com", "wsj.com",
    "axios.com", "morningbrew.com", "cnbc.com", "newsweek.com",
    "businessinsider.com", "fastcompany.com", "fortune.com",
    "theverge.com", "forbes.com",
}

EU_SIGNALS = {
    "europe", "european", " eu ", "euro",
    "uk", "united kingdom", "france", "germany", "spain", "italy",
    "netherlands", "poland", "czech", "slovakia", "hungary", "romania",
    "bulgaria", "croatia", "sweden", "denmark", "norway", "finland",
    "belgium", "austria", "switzerland", "portugal", "ireland", "greece",
    "latvia", "lithuania", "estonia", "slovenia", "serbia", "ukraine",
    "london", "paris", "berlin", "amsterdam", "madrid", "rome", "warsaw",
    "prague", "budapest", "bucharest", "stockholm", "copenhagen", "dublin",
    "brussels", "vienna", "zurich", "lisbon", "milan", "barcelona",
    "deliverect", "restimo", "restaumatic", "upmenu", "sunday.app",
    "choice restaurant", "choice crm", "choice.app", "choiceqr",
}

EU_SPECIFIC_MARKERS = (
    ".eu", "sifted", "euronews", "euractiv", "eu-startups",
    "tech.eu", "maddyness", "siliconcanals", "therecursive",
    "netokracija", "bebeez", "startupreporter", "dispatcheseurope",
    "vestbee", "itkey", "cybernews", "techfundingnews", "startuprise",
)


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def _is_eu_relevant(domain: str, title: str) -> bool:
    for us in US_ONLY_DOMAINS:
        if us in domain:
            return False
    for marker in EU_SPECIFIC_MARKERS:
        if marker in domain:
            return True
    title_lower = f" {title.lower()} "
    return any(signal in title_lower for signal in EU_SIGNALS)


def _is_english(title: str) -> bool:
    if not title:
        return False
    non_latin = sum(1 for c in title if ord(c) > 0x024F)
    return non_latin / max(len(title), 1) < 0.2


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Tool 1: search_articles
# ---------------------------------------------------------------------------

def search_articles(query: str, days: int = 90) -> list[dict]:
    """
    Search Google News RSS for EU-relevant English articles.
    Returns a list of article dicts: title, url, portal, published.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(query + ' after:' + since)}&hl=en-GB&gl=GB&ceid=GB:en"
    )

    raw: list[dict] = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            title  = entry.get("title", "")
            url    = entry.get("link", "")
            pub    = (entry.get("published", "") or "")[:10]
            portal = entry.get("source", {}).get("title", "")
            domain = _domain_from_url(url)

            if not url or not title:
                continue
            if not _is_english(title):
                continue
            if not _is_eu_relevant(domain, title):
                continue

            raw.append({
                "title":     title,
                "url":       url,
                "published": pub,
                "portal":    portal or domain.split(".")[0].title(),
            })
    except Exception as exc:
        logger.error("RSS search error for '%s': %s", query, exc)

    # Deduplicate by URL
    seen: set[str] = set()
    results: list[dict] = []
    for r in raw:
        if r["url"] not in seen:
            seen.add(r["url"])
            results.append(r)

    logger.info("search_articles('%s', %d days) → %d results", query, days, len(results))
    return results[:MAX_SEARCH_RESULTS]


# ---------------------------------------------------------------------------
# Tool 2: send_articles_to_group
# ---------------------------------------------------------------------------

def send_articles_to_group(articles: list[dict], chat_id: str) -> str:
    """Post each article as a Telegram message to the group."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return "Error: TELEGRAM_BOT_TOKEN not set."
    if not articles:
        return "No articles to send."

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent = 0
    for a in articles:
        text = (
            f"📰 <b>{_escape_html(a['title'])}</b>\n"
            f"🌐 {_escape_html(a.get('portal', '—'))}  "
            f"📅 {a.get('published', '—')}\n"
            f"🔗 {a['url']}"
        )
        try:
            resp = requests.post(
                api_url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=10,
            )
            if resp.json().get("ok"):
                sent += 1
            time.sleep(0.4)
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)

    return f"Done — sent {sent} of {len(articles)} articles to the group."


# ---------------------------------------------------------------------------
# Tool 3: create_sheet_tab
# ---------------------------------------------------------------------------

def create_sheet_tab(query: str, articles: list[dict]) -> str:
    """Create a new worksheet tab in the AgentPR Articles spreadsheet."""
    sa_json_raw    = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")

    if not sa_json_raw or not spreadsheet_id:
        return "Error: Google Sheets credentials not configured."
    if not articles:
        return "No articles to save."

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(
            json.loads(sa_json_raw),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(spreadsheet_id)

        tab_name = f"{query[:22].strip()} {datetime.now().strftime('%m/%d %H:%M')}"
        ws = sh.add_worksheet(title=tab_name, rows=200, cols=6)

        ws.append_row(["Article Name", "Article Link", "Portal", "Date Published", "Date Found"])
        ws.format("A1:E1", {"textFormat": {"bold": True}})

        today = datetime.now().strftime("%Y-%m-%d")
        ws.append_rows(
            [[a["title"], a["url"], a.get("portal", ""), a.get("published", ""), today]
             for a in articles],
            value_input_option="USER_ENTERED",
        )

        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        logger.info("Created tab '%s' with %d rows.", tab_name, len(articles))
        return f"Created tab '{tab_name}' with {len(articles)} articles.\nOpen here: {sheet_url}"

    except Exception as exc:
        logger.error("create_sheet_tab failed: %s", exc)
        return f"Error creating sheet tab: {exc}"


# ---------------------------------------------------------------------------
# Anthropic tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "search_articles",
        "description": (
            "Search for EU/European news articles in English on a given topic. "
            "Use this whenever the user asks to find, search, or show articles. "
            "After the search, show a numbered summary and ALWAYS ask: "
            "'Found X articles. Where should I send them?\n"
            "1️⃣ Here in the group\n2️⃣ New Google Sheet tab' "
            "— do NOT call send_to_group or create_sheet_tab until the user replies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search topic, e.g. 'Deliverect funding Europe', 'AI restaurants'",
                },
                "days": {
                    "type": "integer",
                    "description": "How many days back to search. Default 90 (3 months).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "send_to_group",
        "description": (
            "Post the previously found articles as Telegram messages in this group. "
            "Only call this after the user explicitly chose option 1 or said "
            "'here', 'group', 'send here', 'post here', or '1'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_sheet_tab",
        "description": (
            "Save the previously found articles to a new tab in the AgentPR Articles "
            "Google Sheet and return the link. "
            "Only call this after the user explicitly chose option 2 or said "
            "'sheet', 'google sheet', 'spreadsheet', or '2'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
