"""
AgentPR — automated news monitor for restaurant tech / competitors.

Run order:
  1. Load seen URLs from Google Sheets (dedup state)
  2. Fetch articles from Google News RSS (all keyword groups)
  3. Fetch articles from NewsAPI (Tier 1 domains)
  4. Probe direct RSS feeds for Tier 2 + Tier 3 domains
  5. Filter: date >= CUTOFF_DATE and URL not already seen
  6. For each new article: append to Google Sheets + send Telegram message
"""

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

from sheets import append_articles, load_seen_urls, split_author_name

SEEN_URLS_FILE = os.path.join(os.path.dirname(__file__), "seen_urls.json")
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
        # Unknown date — exclude to avoid surfacing old articles
        return False
    return dt >= CUTOFF_DT


def _is_eu_relevant(article: dict) -> bool:
    """
    Returns True if the article is relevant to the EU/European market.
    Hard-blocks known US-only domains. For international domains, requires
    at least one EU signal in the title.
    """
    domain = article.get("_domain", "")

    # Hard-block US-only outlets
    for us_domain in US_ONLY_DOMAINS:
        if us_domain in domain:
            return False

    # Google News RSS is already geo-targeted to GB/EU (gl=GB),
    # so anything that isn't from a US-only domain is considered EU-relevant.
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
    """Convert domain to a human-readable portal name."""
    name = domain.replace("www.", "").split(".")[0]
    return name.replace("-", " ").title()


_COMPANY_KEYWORDS = {
    "Deliverect": ["deliverect"],
    "Sunday": ["sunday.app", "sundayapp", "sunday app restaurant"],
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


def _match_company(text: str) -> str:
    """Return the most prominently mentioned tracked company name."""
    text_lower = text.lower()
    for company, keywords in _COMPANY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return company
    return "Restaurant Tech"


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

        # Try meta tags first (fastest)
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

        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
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

        # Byline patterns in HTML
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
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


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

    # Capture description/summary for richer notifications
    raw_desc = entry.get("description") or entry.get("summary") or ""
    description = _strip_html(raw_desc)[:300]

    domain = _domain_from_url(url)
    if not portal:
        portal = _portal_name_from_domain(domain)

    combined_text = f"{title} {query}"
    company = _match_company(combined_text)

    author_first, author_last = split_author_name(author_raw)

    article = {
        "title": title,
        "url": url,
        "description": description,
        "company": company,
        "author_first": author_first,
        "author_last": author_last,
        "author_email": "",
        "country": _country_for_domain(domain),
        "portal": portal,
        "published_date": pub_date[:10] if pub_date else "",
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
    # Use UK geo (English + European coverage) instead of US
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
            time.sleep(0.3)  # polite crawl delay
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
    # NewsAPI accepts max 20 domains at once
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

        # Try probing known RSS paths
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
            # Fall back to Google News RSS site: query
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
                # Only keep articles that mention tracked topics
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
# Author enrichment
# ---------------------------------------------------------------------------

def enrich_authors(articles: list[dict]) -> list[dict]:
    """
    For articles missing an author, attempt to scrape it from the article page.
    Limits scraping to avoid long runtimes.
    """
    enriched = []
    scrape_budget = 30  # max pages to scrape per run

    for article in articles:
        if not article["author_first"] and scrape_budget > 0:
            author = _scrape_author_from_url(article["url"])
            if author:
                first, last = split_author_name(author)
                article["author_first"] = first
                article["author_last"] = last
            scrape_budget -= 1
        enriched.append(article)

    return enriched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_seen_urls_local() -> set:
    """Load seen URLs from the local JSON file committed in the repo."""
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_seen_urls_local(urls: set) -> None:
    """Persist seen URLs to the local JSON file."""
    try:
        with open(SEEN_URLS_FILE, "w") as f:
            json.dump(sorted(urls), f, indent=2)
    except Exception as exc:
        logger.error("Failed to save seen_urls.json: %s", exc)


def run():
    logger.info("=== AgentPR run started ===")

    # Step 1: load seen URLs from local file (primary) + Sheets (if configured)
    seen_urls = _load_seen_urls_local()
    seen_urls.update(load_seen_urls())
    logger.info("Loaded %d already-seen URLs total.", len(seen_urls))

    # Step 2: collect raw candidates
    raw: list[dict] = []

    raw += fetch_google_news_rss(ALL_QUERIES)
    raw += fetch_newsapi(ALL_QUERIES, TIER1_DOMAINS)
    raw += fetch_direct_rss(TIER2_DOMAINS + TIER3_DOMAINS)

    logger.info("Total raw candidates before filtering: %d", len(raw))

    # Step 3: deduplicate, filter by date, EU relevance, and English language
    seen_in_run: set[str] = set()
    new_articles: list[dict] = []

    for article in raw:
        url = article["url"].strip()
        if not url:
            continue
        if url in seen_urls or url in seen_in_run:
            continue
        if not _is_after_cutoff(article.get("published_date")):
            logger.debug("Skipped (old date): %s", article.get("title", "")[:60])
            continue
        if not _is_eu_relevant(article):
            logger.debug("Skipped (not EU): %s | %s", article.get("_domain", ""), article.get("title", "")[:60])
            continue
        seen_in_run.add(url)
        new_articles.append(article)

    logger.info("New articles after dedup + date + EU relevance filter: %d", len(new_articles))

    # Step 4: enrich missing authors via page scraping
    new_articles = enrich_authors(new_articles)

    # Step 5: persist seen URLs locally so next run skips them
    all_seen = seen_urls | {a["url"] for a in new_articles}
    _save_seen_urls_local(all_seen)

    # Step 6: write to Sheets (optional) + notify Telegram
    written = append_articles(new_articles)
    if written:
        logger.info("Wrote %d articles to Google Sheets.", written)

    for article in new_articles:
        send_article(article)
        time.sleep(0.5)  # avoid Telegram rate limit

    send_summary(len(new_articles))
    logger.info("=== AgentPR run complete. %d new articles. ===", len(new_articles))


if __name__ == "__main__":
    run()
