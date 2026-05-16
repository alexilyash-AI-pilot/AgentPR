import difflib
import json
import logging
import os
from datetime import datetime
from typing import Optional

# gspread is optional — Sheets logging is skipped if credentials are not configured
try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_AVAILABLE = True
except ImportError:
    _GSPREAD_AVAILABLE = False

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = [
    "Date Added",
    "Publication Date",
    "Article Title",
    "Company Mentions",
    "Short Summary",
    "Portal Name",
    "Article URL",
    "Status",
    "First Detected Time",
]

# Column indices (1-based) used for direct cell operations
_COL_URL = 7
_COL_STATUS = 8


def sheets_enabled() -> bool:
    return (
        _GSPREAD_AVAILABLE
        and bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
        and bool(os.environ.get("SPREADSHEET_ID"))
    )


def _get_client():
    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_worksheet(client):
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet = client.open_by_key(spreadsheet_id)
    try:
        ws = sheet.worksheet("Articles")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Articles", rows=5000, cols=len(SHEET_HEADERS))

    # Initialize headers only when the sheet is completely empty
    existing = ws.get_all_values()
    if not existing:
        ws.append_row(SHEET_HEADERS, value_input_option="RAW")
        logger.info("Initialized 'Articles' worksheet with new headers.")

    return ws


def get_all_articles() -> list[dict]:
    """Return all rows from sheet as list of dicts keyed by column name."""
    if not sheets_enabled():
        logger.info("Google Sheets not configured — returning empty article list.")
        return []
    try:
        client = _get_client()
        ws = _get_worksheet(client)
        return ws.get_all_records()
    except Exception as exc:
        logger.error("get_all_articles failed: %s", exc)
        return []


def is_duplicate(url: str, title: str, existing: list[dict]) -> bool:
    """Return True if URL matches exactly OR title similarity > 0.85."""
    url_clean = url.strip()
    title_lower = title.lower().strip()
    for row in existing:
        if row.get("Article URL", "").strip() == url_clean:
            return True
        existing_title = row.get("Article Title", "").lower().strip()
        if existing_title and title_lower:
            ratio = difflib.SequenceMatcher(None, title_lower, existing_title).ratio()
            if ratio > 0.85:
                return True
    return False


def append_article(article: dict) -> bool:
    """Append one article row. Returns True on success."""
    if not sheets_enabled():
        return False
    try:
        client = _get_client()
        ws = _get_worksheet(client)
        now = datetime.utcnow().isoformat()
        row = [
            article.get("date_added", now),
            article.get("publication_date", ""),
            article.get("title", ""),
            article.get("company_mentions", ""),
            article.get("short_summary", ""),
            article.get("portal", ""),
            article.get("url", ""),
            article.get("status", "Not Sent"),
            article.get("first_detected_time", now),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.debug("Appended article: %s", article.get("title", "")[:60])
        return True
    except Exception as exc:
        logger.error("append_article failed: %s", exc)
        return False


def mark_sent(url: str) -> bool:
    """Find row by URL and update Status to 'Sent'. Returns True on success."""
    if not sheets_enabled():
        return False
    try:
        client = _get_client()
        ws = _get_worksheet(client)
        url_col = ws.col_values(_COL_URL)
        url_clean = url.strip()
        for i, cell_url in enumerate(url_col):
            if cell_url.strip() == url_clean:
                row_idx = i + 1  # gspread rows are 1-indexed
                ws.update_cell(row_idx, _COL_STATUS, "Sent")
                logger.debug("Marked row %d as Sent.", row_idx)
                return True
        logger.warning("mark_sent: URL not found in sheet: %s", url[:80])
        return False
    except Exception as exc:
        logger.error("mark_sent failed: %s", exc)
        return False


def split_author_name(full_name: Optional[str]) -> tuple[str, str]:
    """Split 'First Last' into ('First', 'Last'). Handles missing/extra parts gracefully."""
    if not full_name:
        return "", ""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])
