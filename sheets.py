import os
import json
import logging
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = [
    "Article Name",
    "Article Link",
    "Company",
    "Editor Name",
    "Editor Surname",
    "Editor Email",
    "Country",
    "Portal Name",
    "Date Published",
    "Date Found",
]


def _get_client() -> gspread.Client:
    """Build an authenticated gspread client from the env-injected service account JSON."""
    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_worksheet(client: gspread.Client) -> gspread.Worksheet:
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    sheet = client.open_by_key(spreadsheet_id)
    try:
        ws = sheet.worksheet("Articles")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Articles", rows=5000, cols=len(SHEET_HEADERS))
        ws.append_row(SHEET_HEADERS, value_input_option="RAW")
        logger.info("Created 'Articles' worksheet with headers.")
    return ws


def load_seen_urls() -> set:
    """Return the set of article URLs already logged in the sheet."""
    try:
        client = _get_client()
        ws = _get_worksheet(client)
        # Column B (index 1) is Article Link
        links = ws.col_values(2)
        # Skip header row
        return set(url.strip() for url in links[1:] if url.strip())
    except Exception as exc:
        logger.error("Failed to load seen URLs from Sheets: %s", exc)
        return set()


def append_articles(articles: list[dict]) -> int:
    """
    Append a list of article dicts to the sheet.
    Each dict must have keys matching SHEET_HEADERS (snake_case accepted too).
    Returns the count of rows actually written.
    """
    if not articles:
        return 0

    try:
        client = _get_client()
        ws = _get_worksheet(client)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        rows = []
        for a in articles:
            rows.append([
                a.get("title", ""),
                a.get("url", ""),
                a.get("company", ""),
                a.get("author_first", ""),
                a.get("author_last", ""),
                a.get("author_email", ""),
                a.get("country", ""),
                a.get("portal", ""),
                a.get("published_date", ""),
                today,
            ])
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info("Appended %d rows to Google Sheets.", len(rows))
        return len(rows)
    except Exception as exc:
        logger.error("Failed to append articles to Sheets: %s", exc)
        return 0


def split_author_name(full_name: Optional[str]) -> tuple[str, str]:
    """Split 'First Last' into ('First', 'Last'). Handles missing/extra parts gracefully."""
    if not full_name:
        return "", ""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])
