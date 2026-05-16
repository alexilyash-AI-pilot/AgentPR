"""
AgentPR — automated news monitor for restaurant tech / competitors.

Run order:
  1. Fetch articles from all sources (Google News RSS, NewsAPI, direct RSS)
  2. Load existing articles from Google Sheets for deduplication
     (falls back to seen_urls.json when Sheets credentials are unavailable)
  3. For each new article: append to Sheets → send Telegram → mark Sent
  4. Log summary: X new articles found, Y sent
"""

import difflib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from sheets import (
    append_article,
    get_all_articles,
    is_duplicate,
    mark_sent,
    sheets_enabled,
    split_author_name,
)
from sources import (
    ALL_QUERIES,
    CUTOFF_DATE,
    DOMAIN_COUNTRY_MAP,
    EU_SIGNALS,
    RSS_PATHS,
    TIER1_DOMAINS,
    TIER2_DOMAINS,
    TIER3_DOMAINS,
    US_ONLY_DOMAINS,
    KEYWORD_GROUPS,
)
from telegram_bot import send_article, send_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SEEN_URLS_FILE = os.path.join(os.path.dirname(__file__), "seen_urls.json")
CUTOFF_DT = datetime.fromisoformat(CUTOFF_DATE).replace(tzinfo=timezone.utc)
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AgentPR/1.0; +https://github.com/agentpr)"
    )
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(date_str)])
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _is_after_cutoff(date_str: Optional[str]) -> bool:
    dt = _parse_date(date_str)
    if dt is None:
        return False
    return dt >= CUTOFF_DT


def _is_eu_relevant(article: dict) -> bool:
    """
    Returns True if the article is relevant to the EU/European market.
    Hard-blocks known US-only domains. Google News RSS is geo-targeted to
    GB/EU (gl=GB), so anything not from a US-only domain is considered relevant.
    """
    domain = article.get("_domain", "")
    for us_domain in US_ONLY_DOMAINS:
        if us_domain in domain:
            return False
    return True


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def _country_for_domain(domain: str) -> str:
    for key, country in DOMAIN_COUNTRY_MAP.items():
        if key in domain:
            return country
    tld = domain.rsplit(".", 1)[-1].upper()
    tld_map = {
        "PL": "Poland", "DE": "Germany", "FR": "France", "IT": "Italy",
        "ES": "Spain", "CZ": "Czech Republic", "SK": "Slovakia",
        "HU": "Hungary", "RO": "Romania", "HR": "Croatia", "EU": "Europe",
        "UK": "UK", "CO": "International", "IO": "International",
    }
    return tld_map.get(tld, "International")


def _portal_name_from_domain(domain: str) -> str:
    name = domain.replace("www.", "").split(".")[0]
    return name.replace("-", " ").title()


_COMPANY_KEYWORDS = {
    "Deliverect": ["deliverect"],
    "Sunday": ["sunday.app", "sundayapp", "sunday app qr", "sunday app payment"],
    "Flipdish": ["flipdish"],
    "StoreKit": ["storekit"],
    "UpMenu": ["upmenu"],
    "Restimo": ["restimo"],
    "Restaumatic": ["restaumatic"],
    "TheFork": ["thefork", "the fork restaurant"],
    "OpenTable": ["opentable"],
    "Quandoo": ["quandoo"],
    "Tableo": ["tableo"],
    "ResDiary": ["resdiary"],
    "Zenchef": ["zenchef"],
    "Eat App": ["eat app", "eatapp"],
    "SevenRooms": ["sevenrooms"],
    "Otter": ["tryotter", "otter restaurant"],
    "TableQR": ["tableqr"],
    "MENU TIGER": ["menutiger", "menu tiger"],
    "ChoiceQR": ["choiceqr", "choice.app", "choice restaurant", "choice crm"],
}


def _match_companies(text: str) -> list[str]:
    """Return all tracked company names mentioned in text."""
    text_lower = text.lower()
    matches = []
    for company, keywords in _COMPANY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                matches.append(company)
                break
    return matches if matches else ["Restaurant Tech"]


def _why_it_matters(article: dict) -> str:
    """Derive a one-sentence strategic insight from the article content."""
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    if any(w in text for w in ["funding", "series a", "series b", "series c", "seed round", "raised", "investment", "investor", "venture"]):
        return "Signals new investment activity in the restaurant tech space."
    if any(w in text for w in ["acqui", "merger", "bought", "purchase", "takeover"]):
        return "Indicates consolidation in the restaurant technology market."
    if any(w in text for w in ["partnership", "partner", "integration", "integrates", "integrating"]):
        return "Suggests strategic partnership or product integration expanding market reach."
    if any(w in text for w in ["artificial intelligence", "machine learning", "llm", "generative ai", " ai "]):
        return "Highlights AI adoption and innovation trends in the hospitality sector."
    if any(w in text for w in ["pos integration", "point of sale"]):
        return "Signals product expansion through new POS integrations."
    if any(w in text for w in ["qr order", "qr menu", "qr code"]):
        return "Shows growth in contactless QR ordering and menu technology."
    if any(w in text for w in ["reservation", "booking", "table management"]):
        return "Indicates competition in the restaurant reservations and table management space."
    if any(w in text for w in ["delivery", "takeaway", "takeout"]):
        return "Highlights delivery management feature development and market activity."
    if any(w in text for w in ["loyalty", "crm", "guest retention", "guest data"]):
        return "Signals focus on guest retention and loyalty technology."
    if any(w in text for w in ["launch", "new product", "feature release", "announced"]):
        return "Indicates new product innovation in hospitality tech."
    if any(w in text for w in ["expansion", "enterprise", "new market", "international"]):
        return "Suggests market expansion or enterprise growth strategy."
    if any(w in text for w in ["ceo", "cto", "coo", "hire", "appoint", "executive", "joins"]):
        return "Strategic executive change may signal a new company direction."
    return "Noteworthy development in the restaurant technology landscape."


def _scrape_author_from_url(url: str) -> Optional[str]:
    """
    Attempt to extract author name from article page via common meta tags.
    Returns full name string or None.
    """
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=8)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        for attr, val in [
            ("name", "author"),
            ("property", "article:author"),
            ("name", "dc.creator"),
            ("property", "og:author"),
            ("name", "byl"),
        ]:
            tag = soup.find("meta", {attr: val})
            if tag and tag.get("content"):
                return tag["content"].strip()

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0]
                author = data.get("author")
                if isinstance(author, dict):
                    return author.get("name", "")
                if isinstance(author, list) and author:
                    return author[0].get("name", "")
                if isinstance(author, str):
                    return author
            except Exception:
                continue

        byline = soup.find(class_=re.compile(r"author|byline|writer", re.I))
        if byline:
            text = byline.get_text(separator=" ").strip()
            text = re.sub(r"^(By|Author[:\s]*)", "", text, flags=re.I).strip()
            if text and len(text) < 80:
                return text

    except Exception:
        pass
    return None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _source_tier(domain: str) -> int:
    """Return the authority tier (1=best … 4=unknown) for a given domain."""
    for d in TIER1_DOMAINS:
        if d in domain:
            return 1
    for d in TIER2_DOMAINS:
        if d in domain:
            return 2
    for d in TIER3_DOMAINS:
        if d in domain:
            return 3
    return 4


def _deduplicate_by_story(articles: list[dict]) -> list[dict]:
    """
    Within-run story clustering: group articles that cover the same story and
    keep only the one from the most authoritative source.

    Two articles are considered the same story when either:
      - Their titles have a SequenceMatcher ratio > 0.70, OR
      - 3+ consecutive words from one title appear as a phrase in the other.

    Within each cluster the winner is the article with the lowest tier number;
    ties are broken by longest description.
    """
    def _titles_match(t1: str, t2: str) -> bool:
        t1_l, t2_l = t1.lower(), t2.lower()
        if difflib.SequenceMatcher(None, t1_l, t2_l).ratio() > 0.70:
            return True
        for words in (t1_l.split(), t2_l.split()):
            other = t2_l if words is t1_l.split() else t1_l
            if len(words) >= 3:
                for i in range(len(words) - 2):
                    if " ".join(words[i : i + 3]) in other:
                        return True
        return False

    assigned = [False] * len(articles)
    clusters: list[list[dict]] = []

    for i, article in enumerate(articles):
        if assigned[i]:
            continue
        cluster = [article]
        assigned[i] = True
        for j in range(i + 1, len(articles)):
            if not assigned[j] and _titles_match(article["title"], articles[j]["title"]):
                cluster.append(articles[j])
                assigned[j] = True
        clusters.append(cluster)

    result = []
    for cluster in clusters:
        best = min(
            cluster,
            key=lambda a: (
                _source_tier(a.get("_domain", "")),
                -len(a.get("description", "")),
            ),
        )
        if len(cluster) > 1:
            dropped = [a["title"][:60] for a in cluster if a is not best]
            logger.info(
                "Story dedup: kept '%s' (%s tier %d), dropped %d: %s",
                best["title"][:60],
                best.get("_domain", ""),
                _source_tier(best.get("_domain", "")),
                len(dropped),
                dropped,
            )
        result.append(best)

    return result


def _build_article(entry: dict, query: str = "") -> dict:
    """Normalise a feedparser entry or NewsAPI article into our internal dict."""
    url = entry.get("url") or entry.get("link", "")
    title = entry.get("title", "")
    author_raw = entry.get("author") or entry.get("author_detail", {}).get("name", "")
    pub_date = entry.get("published") or entry.get("publishedAt", "")
    source = entry.get("source", {})
    if isinstance(source, dict):
        portal = source.get("name", "")
    else:
        portal = str(source)

    raw_desc = entry.get("description") or entry.get("summary") or ""
    description = _strip_html(raw_desc)[:300]

    domain = _domain_from_url(url)
    if not portal:
        portal = _portal_name_from_domain(domain)

    combined_text = f"{title} {query}"
    companies = _match_companies(combined_text)

    author_first, author_last = split_author_name(author_raw)

    article = {
        "title": title,
        "url": url,
        "description": description,
        "companies": companies,
        "company": companies[0],
        "author_first": author_first,
        "author_last": author_last,
        "author_email": "",
        "country": _country_for_domain(domain),
        "portal": portal,
        "published_date": pub_date,  # keep full string; _is_after_cutoff handles all formats
        "_domain": domain,
        "_author_raw": author_raw,
    }
    article["why_it_matters"] = _why_it_matters(article)
    return article


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_google_news_rss(queries: list[str]) -> list[dict]:
    """Fetch articles from Google News RSS for each query, using EU geo."""
    results = []
    base = "https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en"

    for query in queries:
        url = base.format(query=quote_plus(query))
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                article = _build_article(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "author": entry.get("author", ""),
                        "description": entry.get("summary", ""),
                        "source": {"name": entry.get("source", {}).get("title", "")},
                    },
                    query=query,
                )
                if article["url"]:
                    results.append(article)
            logger.info("Google News RSS [%s]: %d entries", query, len(feed.entries))
            time.sleep(0.3)
        except Exception as exc:
            logger.warning("Google News RSS failed for query '%s': %s", query, exc)

    return results


def fetch_newsapi(queries: list[str], domains: list[str]) -> list[dict]:
    """Fetch from NewsAPI /v2/everything filtered by domain list."""
    api_key = os.environ.get("NEWSAPI_KEY", "")
    if not api_key:
        logger.warning("NEWSAPI_KEY not set — skipping NewsAPI fetch.")
        return []

    results = []
    domain_chunks = [domains[i:i+20] for i in range(0, len(domains), 20)]
    endpoint = "https://newsapi.org/v2/everything"

    for query in queries:
        for chunk in domain_chunks:
            params = {
                "q": query,
                "domains": ",".join(chunk),
                "from": CUTOFF_DATE,
                "sortBy": "publishedAt",
                "pageSize": 50,
                "apiKey": api_key,
            }
            try:
                resp = requests.get(endpoint, params=params, timeout=10)
                if resp.status_code == 426:
                    logger.warning("NewsAPI: upgrade required (free tier limit hit).")
                    return results
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("articles", []):
                    article = _build_article(item, query=query)
                    if article["url"]:
                        results.append(article)
                logger.info(
                    "NewsAPI [%s / %d domains]: %d articles",
                    query, len(chunk), len(data.get("articles", [])),
                )
                time.sleep(0.2)
            except Exception as exc:
                logger.warning("NewsAPI failed [%s]: %s", query, exc)

    return results


def fetch_direct_rss(domains: list[str]) -> list[dict]:
    """Probe common RSS paths for Tier 2/3 domains and parse feeds."""
    results = []
    for domain in domains:
        feed_url = None

        for path in RSS_PATHS:
            candidate = f"https://{domain}{path}"
            try:
                resp = requests.head(candidate, headers=REQUEST_HEADERS, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    feed_url = candidate
                    break
            except Exception:
                continue

        if not feed_url:
            site_query = f"site:{domain}"
            feed_url = f"https://news.google.com/rss/search?q={quote_plus(site_query)}&hl=en"

        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                article = _build_article(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "author": entry.get("author", ""),
                        "description": entry.get("summary", ""),
                        "source": {"name": feed.feed.get("title", domain)},
                    }
                )
                full_text = f"{article['title']}".lower()
                tracked_terms = [
                    kw.lower() for group in KEYWORD_GROUPS.values() for kw in group
                ]
                if any(term in full_text for term in tracked_terms):
                    results.append(article)
            logger.info("Direct RSS [%s]: %d relevant entries", domain, len(feed.entries))
        except Exception as exc:
            logger.warning("Direct RSS failed [%s]: %s", domain, exc)

        time.sleep(0.2)

    return results


# ---------------------------------------------------------------------------
# Fallback: local seen_urls.json (used when Sheets is unavailable)
# ---------------------------------------------------------------------------

def _load_seen_urls_local() -> set:
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_seen_urls_local(urls: set) -> None:
    try:
        with open(SEEN_URLS_FILE, "w") as f:
            json.dump(sorted(urls), f, indent=2)
    except Exception as exc:
        logger.error("Failed to save seen_urls.json: %s", exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    logger.info("=== AgentPR run started ===")

    # Step 1: fetch all raw candidates
    raw: list[dict] = []
    raw += fetch_google_news_rss(ALL_QUERIES)
    raw += fetch_newsapi(ALL_QUERIES, TIER1_DOMAINS)
    raw += fetch_direct_rss(TIER2_DOMAINS + TIER3_DOMAINS)
    logger.info("Total raw candidates before filtering: %d", len(raw))

    # Step 2: load existing articles for deduplication
    use_sheets = sheets_enabled()
    if use_sheets:
        existing = get_all_articles()
        logger.info("Loaded %d existing articles from Google Sheets.", len(existing))
        seen_urls_local: set = set()
    else:
        existing = []
        seen_urls_local = _load_seen_urls_local()
        logger.info(
            "Sheets not available — loaded %d seen URLs from local fallback.",
            len(seen_urls_local),
        )

    # Step 3: filter & cross-run dedup by URL/title; collect new articles
    seen_in_run: set[str] = set()
    new_articles: list[dict] = []

    for article in raw:
        url = article["url"].strip()
        if not url:
            continue
        if not _is_after_cutoff(article.get("published_date")):
            logger.debug("Skipped (old date): %s", article.get("title", "")[:60])
            continue
        if not _is_eu_relevant(article):
            logger.debug("Skipped (not EU): %s | %s", article.get("_domain", ""), article.get("title", "")[:60])
            continue
        if url in seen_in_run:
            continue

        title = article.get("title", "")

        if use_sheets:
            if is_duplicate(url, title, existing):
                logger.debug("Duplicate (Sheets): %s", title[:60])
                continue
        else:
            if url in seen_urls_local:
                logger.debug("Duplicate (local): %s", title[:60])
                continue

        seen_in_run.add(url)
        new_articles.append(article)

        # Persist immediately as "Not Sent" — all unique articles are recorded
        # regardless of whether they survive the within-run story dedup below.
        now_iso = datetime.utcnow().isoformat()
        companies = article.get("companies", [article.get("company", "Restaurant Tech")])
        sheet_row = {
            "date_added": now_iso,
            "publication_date": article.get("published_date", ""),
            "title": title,
            "company_mentions": ", ".join(companies),
            "short_summary": article.get("description", "")[:200],
            "portal": article.get("portal", ""),
            "url": url,
            "status": "Not Sent",
            "first_detected_time": now_iso,
        }
        if use_sheets:
            append_article(sheet_row)
        else:
            seen_urls_local.add(url)

    new_count = len(new_articles)
    logger.info("New articles after cross-run dedup: %d", new_count)

    # Step 4: within-run story dedup — one best-source article per story cluster
    to_send = _deduplicate_by_story(new_articles)
    logger.info(
        "After story dedup: %d to send (%d suppressed as lower-authority duplicates)",
        len(to_send),
        new_count - len(to_send),
    )

    # Step 5: send to Telegram; mark sent only for the articles actually sent
    # Cap at 50 per run to avoid flooding on first/catch-up runs.
    # Telegram group rate limit: ~20 messages/min → sleep 3 s between sends.
    MAX_SEND_PER_RUN = 50
    send_batch = to_send[:MAX_SEND_PER_RUN]
    if len(to_send) > MAX_SEND_PER_RUN:
        logger.info(
            "Capping Telegram sends at %d (skipping %d lower-priority articles this run).",
            MAX_SEND_PER_RUN, len(to_send) - MAX_SEND_PER_RUN,
        )

    sent_count = 0
    for article in send_batch:
        sent = send_article(article)
        if sent:
            sent_count += 1
            if use_sheets:
                mark_sent(article["url"])
        time.sleep(3)  # respect Telegram group rate limit (~20 msg/min)

    # Persist fallback state when Sheets is unavailable
    if not use_sheets:
        _save_seen_urls_local(seen_urls_local)

    # Step 6: summary
    send_summary(new_count)
    logger.info(
        "=== AgentPR run complete. %d new articles found, %d sent. ===",
        new_count,
        sent_count,
    )


if __name__ == "__main__":
    run()
