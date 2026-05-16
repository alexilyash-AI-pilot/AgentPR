"""
AgentPR Telegram Bot Handler

Polls Telegram every 15 minutes for commands from the group and responds
with on-demand article searches.

Commands:
  /search <query> [timeframe]  — find EU articles on any topic
  /help                        — show available commands
  /status                      — show agent status

Timeframe examples:
  /search deliverect 12 months
  /search AI restaurants last year
  /search upmenu 3 months
  /search sunday.app last week

Default timeframe: 3 months (90 days).
Only EU / European articles in English are returned.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
OFFSET_FILE  = os.path.join(os.path.dirname(__file__), "bot_offset.json")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"
MAX_RESULTS  = 8

# ---------------------------------------------------------------------------
# EU / language filters (mirrors sources.py + monitor.py)
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
    "choice restaurant", "choice crm", "choice.app",
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


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def send_message(text: str, parse_mode: str = "HTML") -> None:
    if not TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if not resp.json().get("ok"):
            logger.error("Telegram error: %s", resp.json().get("description"))
    except Exception as exc:
        logger.error("send_message failed: %s", exc)


def get_updates(offset: int) -> list:
    try:
        resp = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 0, "limit": 100},
            timeout=15,
        )
        return resp.json().get("result", [])
    except Exception as exc:
        logger.error("getUpdates failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Offset state (tracks last processed update_id)
# ---------------------------------------------------------------------------

def load_offset() -> int:
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE) as f:
                return json.load(f).get("offset", 0)
        except Exception:
            pass
    return 0


def save_offset(offset: int) -> None:
    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump({"offset": offset}, f)
    except Exception as exc:
        logger.error("Failed to save offset: %s", exc)


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------

def _parse_timeframe(text: str) -> tuple[str, int]:
    """
    Strip a timeframe expression from the end of `text`.
    Returns (cleaned_query, days). Default: 90 days.
    """
    days = 90
    patterns = [
        (r"\b(\d+)\s*months?\s*$",  lambda m: int(m.group(1)) * 30),
        (r"\b(\d+)\s*weeks?\s*$",   lambda m: int(m.group(1)) * 7),
        (r"\b(\d+)\s*days?\s*$",    lambda m: int(m.group(1))),
        (r"\blast\s+year\s*$",      lambda _: 365),
        (r"\bpast\s+year\s*$",      lambda _: 365),
        (r"\blast\s+month\s*$",     lambda _: 30),
        (r"\bpast\s+month\s*$",     lambda _: 30),
        (r"\blast\s+week\s*$",      lambda _: 7),
        (r"\bpast\s+week\s*$",      lambda _: 7),
    ]
    for pattern, calc in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            days = calc(m)
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
            break
    return text, days


def parse_command(text: str) -> tuple[str, int] | None:
    """
    Recognise bot commands. Returns (intent, days) where intent is either
    a search query string or one of the special tokens '__help__' / '__status__'.
    Returns None if the message is not a command directed at the bot.
    """
    text = text.strip()
    lower = text.lower()

    # Only process messages that start with '/' or mention the bot
    if not (lower.startswith("/") or "@choiceprbot" in lower):
        return None

    if re.match(r"^/help", lower):
        return "__help__", 0

    if re.match(r"^/status", lower):
        return "__status__", 0

    m = re.match(r"^/search(@\w+)?\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    raw = m.group(2).strip()
    if not raw:
        send_message(
            "⚠️ Please provide a search query.\n\n"
            "<b>Usage:</b> /search &lt;query&gt; [timeframe]\n\n"
            "<b>Examples:</b>\n"
            "  /search deliverect 12 months\n"
            "  /search AI restaurants last year\n"
            "  /search upmenu 3 months"
        )
        return None

    query, days = _parse_timeframe(raw)
    return query, days


# ---------------------------------------------------------------------------
# Article search
# ---------------------------------------------------------------------------

def search_articles(query: str, days: int) -> list[dict]:
    """
    Search Google News RSS for EU-relevant, English articles matching `query`
    published within the last `days` days.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    search_q = f"{query} after:{since}"
    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(search_q)}&hl=en-GB&gl=GB&ceid=GB:en"
    )

    raw = []
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
                logger.debug("Non-English, skipped: %s", title[:60])
                continue
            if not _is_eu_relevant(domain, title):
                logger.debug("Not EU-relevant, skipped: %s | %s", domain, title[:60])
                continue

            raw.append({
                "title":     title,
                "url":       url,
                "published": pub,
                "portal":    portal or domain.split(".")[0].title(),
                "domain":    domain,
            })
    except Exception as exc:
        logger.error("RSS search error for '%s': %s", query, exc)

    # Deduplicate by URL, preserve order
    seen: set[str] = set()
    results = []
    for r in raw:
        if r["url"] not in seen:
            seen.add(r["url"])
            results.append(r)

    return results[:MAX_RESULTS]


# ---------------------------------------------------------------------------
# Response formatters
# ---------------------------------------------------------------------------

HELP_TEXT = (
    "🤖 <b>AgentPR Bot — Commands</b>\n\n"
    "<b>/search</b> &lt;query&gt; [timeframe]\n"
    "Search EU portals for articles on any topic.\n\n"
    "<b>Examples:</b>\n"
    "  /search deliverect 12 months\n"
    "  /search AI restaurants last year\n"
    "  /search sunday.app 3 months\n"
    "  /search restaurant POS Europe 6 months\n"
    "  /search upmenu last week\n\n"
    "<b>Default timeframe:</b> 3 months\n\n"
    "<b>/status</b>  — show agent status\n"
    "<b>/help</b>    — show this message\n\n"
    "📅 Scheduled scans run every 6 hours automatically.\n"
    "🌍 Only EU / European articles in English are returned."
)

STATUS_TEXT = (
    "✅ <b>AgentPR Status</b>\n\n"
    "🕐 Scheduled scan: every 6 hours\n"
    "🌍 Coverage: EU / European portals only\n"
    "🇬🇧 Language: English only\n"
    "📅 Date filter: 1 May 2026 onwards\n"
    "📊 Results logged to Google Sheet\n"
    "💬 New articles sent here automatically\n\n"
    "Use /search to run an on-demand search."
)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def format_results(query: str, days: int, articles: list[dict]) -> str:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    header = (
        f"🔍 <b>Search: {_escape(query)}</b>\n"
        f"📅 Since: {since}  ({days} days)\n"
        f"📰 EU results: {len(articles)}\n"
        "─────────────────────"
    )

    if not articles:
        return (
            header
            + "\n\n❌ No EU articles found for this query and timeframe.\n\n"
            "Try a broader query or longer timeframe."
        )

    lines = [header]
    for i, a in enumerate(articles, 1):
        lines.append(
            f"\n{i}. <b>{_escape(a['title'])}</b>\n"
            f"   🌐 {_escape(a['portal'])}  📅 {a['published']}\n"
            f"   🔗 {a['url']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set — exiting.")
        return

    offset  = load_offset()
    updates = get_updates(offset)

    if not updates:
        logger.info("No new Telegram updates (offset=%d).", offset)
        return

    new_offset = offset
    for update in updates:
        update_id  = update.get("update_id", 0)
        new_offset = max(new_offset, update_id + 1)

        msg  = update.get("message") or update.get("edited_message") or {}
        text = (msg.get("text") or "").strip()

        if not text:
            continue

        logger.info("Update %d: %s", update_id, text[:100])

        parsed = parse_command(text)
        if parsed is None:
            continue

        intent, days = parsed

        if intent == "__help__":
            send_message(HELP_TEXT)
            continue

        if intent == "__status__":
            send_message(STATUS_TEXT)
            continue

        # On-demand search
        query = intent
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        send_message(
            f"🔍 Searching for <b>{_escape(query)}</b> since {since}…\n"
            "⏳ Please wait a moment."
        )

        articles = search_articles(query, days)
        send_message(format_results(query, days, articles))
        logger.info("Sent %d results for query '%s' (%d days).", len(articles), query, days)

        time.sleep(0.5)

    save_offset(new_offset)
    logger.info("Bot run complete. New offset: %d.", new_offset)


if __name__ == "__main__":
    run()
