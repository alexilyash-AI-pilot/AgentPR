"""
One-off script: remove rows from the Google Sheet that no longer pass
the current _is_about_company() / _is_eu_relevant() filters.

Usage:
  GOOGLE_SERVICE_ACCOUNT_JSON=$(cat /path/to/creds.json) \
  /usr/bin/python3 clean_sheet.py
"""

import json
import os
import re
import sys
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Sheet config
# ---------------------------------------------------------------------------
SPREADSHEET_ID = "1nSkFz_2kUs76LIO_mcl5x0WvhuESyRWJ4bSigOoO5UM"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column indices (0-based) in the data rows returned by get_all_values()
COL_TITLE   = 2   # Article Title
COL_SUMMARY = 4   # Short Summary
COL_URL     = 6   # Article URL

# ---------------------------------------------------------------------------
# Constants copied from sources.py / monitor.py
# ---------------------------------------------------------------------------

TIER1_DOMAINS = [
    "techcrunch.com", "bloomberg.com", "reuters.com", "forbes.com",
    "cnbc.com", "ft.com", "businessinsider.com", "fortune.com",
    "wired.com", "fastcompany.com", "theverge.com", "economist.com",
    "wsj.com", "washingtonpost.com", "nytimes.com", "newsweek.com",
    "observer.com", "sifted.eu", "euronews.com", "euractiv.com",
    "theguardian.com", "dailymail.co.uk", "thetimes.co.uk",
    "politico.com", "cybernews.com",
]

TIER2_DOMAINS = [
    "tech.eu", "vestbee.com", "maddyness.com", "eu-startups.com",
    "therecursive.com", "itkey.media", "techfundingnews.com",
    "dispatcheseurope.com", "siliconcanals.com", "crunchbase.com",
    "news.crunchbase.com", "morningbrew.com", "itlogs.com",
    "startupreporter.eu", "pitchbook.com", "thenextweb.com",
    "restauranttechnologynews.com", "thesaasnews.com", "uktech.news",
    "techround.co.uk", "startups.co.uk", "pathfounders.com",
    "thecaterer.com", "foodnavigator.com", "hospitalitynet.org",
    "big-hosp.co.uk", "gruenderszene.de", "deutsche-startups.de",
    "frenchweb.fr", "elreferente.es", "startupxplore.com",
]

US_ONLY_DOMAINS: set = set()

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
    "deliverect", "sunday.app", "sundayapp", "flipdish", "storekit",
    "upmenu", "restimo", "restaumatic", "thefork", "opentable",
    "quandoo", "tableo", "resdiary", "zenchef", "eat app", "eatapp",
    "sevenrooms", "tryotter", "tableqr", "menutiger", "menu tiger",
    "choiceqr", "choice restaurant", "choice crm", "choice.app",
}

_EU_TLDS = {
    "co.uk", "eu", "de", "fr", "pl", "cz", "sk", "hu", "ro", "hr",
    "at", "be", "nl", "dk", "se", "fi", "no", "pt", "es", "it",
    "lt", "lv", "ee", "si", "bg", "gr", "ie", "lu", "mt",
}

_US_ONLY_SIGNALS = [
    " in the us",
    " across the us",
    "united states restaurant",
    "american restaurant tech",
    "in north america",
]

_LISTICLE_TITLE_PHRASES = [
    "best restaurants",
    "top restaurants",
    "highest-rated restaurants",
    "restaurants in ",
    "restaurants near ",
    "restaurants across ",
    "restaurant guide",
    "dining guide",
    "where to eat",
    "places to eat",
]

_BUSINESS_SIGNALS = [
    "funding", "raises", "raised", "acquisition", "acquires", "acquired",
    "partners", "partnership", "launches", "launch", "new feature",
    "integration", "integrates", "expands", "expansion", "hires", "appoints",
    "appointed", "ceo", "cto", "coo", "series a", "series b", "series c",
    "seed round", "investment", "valuation", "ipo", "merger", "deal",
    "contract", "platform update", "api", "announces", "announced",
]


# ---------------------------------------------------------------------------
# Filter functions (verbatim logic from monitor.py)
# ---------------------------------------------------------------------------

def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def _is_eu_relevant(article: dict) -> bool:
    domain = article.get("_domain", "")
    title = article.get("title", "").lower()
    description = article.get("description", "").lower()
    combined = f"{title} {description}"

    for tld in _EU_TLDS:
        if domain.endswith(f".{tld}"):
            return True

    for d in TIER1_DOMAINS:
        if d in domain:
            return True
    for d in TIER2_DOMAINS:
        if d in domain:
            return True

    if any(signal in combined for signal in EU_SIGNALS):
        return True

    for us_domain in US_ONLY_DOMAINS:
        if us_domain in domain:
            return False

    if any(sig in combined for sig in _US_ONLY_SIGNALS):
        return False

    return True


def _is_about_company(article: dict) -> bool:
    title = article.get("title", "").lower()
    description = article.get("description", "").lower()
    combined = f"{title} {description}"

    has_listicle_phrase = any(phrase in title for phrase in _LISTICLE_TITLE_PHRASES)

    numeric_listicle = bool(
        re.search(r"\b\d+\s+(best|top|highest.rated)\b", title)
        or re.search(r"\b(ranked|ranking|awards)\b.*\brestaurant", title)
        or re.search(r"\brestaurant\b.*\b(ranked|ranking|awards)\b", title)
    )

    is_listicle = has_listicle_phrase or numeric_listicle

    if not is_listicle:
        return True

    has_business_signal = any(signal in combined for signal in _BUSINESS_SIGNALS)
    if has_business_signal:
        return True

    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw_json:
        sys.exit("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON env var not set.")

    info = json.loads(raw_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet("Articles")
    except gspread.WorksheetNotFound:
        sys.exit("ERROR: 'Articles' worksheet not found.")

    all_values = ws.get_all_values()
    if not all_values:
        print("Sheet is empty — nothing to clean.")
        return

    header = all_values[0]
    data_rows = all_values[1:]  # rows 2..N in sheet (1-indexed row = index+2)

    print(f"Total data rows (excluding header): {len(data_rows)}")

    rows_to_delete = []  # will store 1-based sheet row indices

    for i, row in enumerate(data_rows):
        sheet_row_idx = i + 2  # row 1 is header; data starts at row 2

        # Safely read columns (pad if row is shorter than expected)
        def col(idx):
            return row[idx] if idx < len(row) else ""

        title   = col(COL_TITLE)
        summary = col(COL_SUMMARY)
        url     = col(COL_URL)
        domain  = _domain_from_url(url)

        article = {
            "title":       title,
            "description": summary,
            "_domain":     domain,
        }

        passes_company = _is_about_company(article)
        passes_eu      = _is_eu_relevant(article)

        if not passes_company or not passes_eu:
            reason = []
            if not passes_company:
                reason.append("listicle/not-about-company")
            if not passes_eu:
                reason.append("not-EU-relevant")
            print(f"  DELETE row {sheet_row_idx}: [{', '.join(reason)}] {title[:80]!r}")
            rows_to_delete.append(sheet_row_idx)

    kept    = len(data_rows) - len(rows_to_delete)
    deleted = len(rows_to_delete)

    if not rows_to_delete:
        print(f"\nAll {kept} rows pass the filters — nothing to delete.")
        return

    # Delete from bottom to top so earlier row indices remain valid
    for row_idx in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_idx)

    print(f"\nKept {kept} rows, deleted {deleted} rows.")


if __name__ == "__main__":
    main()
