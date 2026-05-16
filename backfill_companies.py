"""
backfill_companies.py — Re-run improved company detection on existing sheet rows.

For each row where Company Mentions is "Restaurant Tech" or empty, runs
_match_companies() against Article Title + Short Summary. If a real company
is detected, updates the Company Mentions cell in place.

Usage:
    GOOGLE_SERVICE_ACCOUNT_JSON=$(cat /path/to/credentials.json) \
    SPREADSHEET_ID=<id> \
    /usr/bin/python3 backfill_companies.py
"""

import json
import logging
import os
import sys
import time

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("gspread / google-auth not installed. Run: pip install gspread google-auth")
    sys.exit(1)

from monitor import _match_companies

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column indices (1-based) matching SHEET_HEADERS in sheets.py
_COL_TITLE = 3
_COL_COMPANY_MENTIONS = 4
_COL_SUMMARY = 5


def _get_worksheet():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        print("GOOGLE_SERVICE_ACCOUNT_JSON env var is not set.")
        sys.exit(1)
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")
    if not spreadsheet_id:
        print("SPREADSHEET_ID env var is not set.")
        sys.exit(1)

    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id)
    try:
        return sheet.worksheet("Articles")
    except gspread.WorksheetNotFound:
        print("Worksheet 'Articles' not found.")
        sys.exit(1)


def main():
    ws = _get_worksheet()

    all_values = ws.get_all_values()
    if not all_values:
        print("Sheet is empty.")
        return

    headers = all_values[0]
    data_rows = all_values[1:]  # skip header row

    updated = 0
    skipped = 0

    for i, row in enumerate(data_rows):
        row_idx = i + 2  # 1-based; +1 for header, +1 for 0-index

        # Pad short rows to avoid index errors
        while len(row) < max(_COL_TITLE, _COL_COMPANY_MENTIONS, _COL_SUMMARY):
            row.append("")

        title = row[_COL_TITLE - 1].strip()
        current_mentions = row[_COL_COMPANY_MENTIONS - 1].strip()
        summary = row[_COL_SUMMARY - 1].strip()

        # Only reprocess rows that have no specific company detected
        if current_mentions and current_mentions.lower() not in ("restaurant tech", ""):
            skipped += 1
            continue

        if not title:
            continue

        companies = _match_companies(title, description=summary)

        if companies == ["Restaurant Tech"]:
            continue  # no improvement

        new_mentions = ", ".join(companies)
        logger.info(
            "Row %d: '%s' → %s",
            row_idx,
            title[:60],
            new_mentions,
        )
        ws.update_cell(row_idx, _COL_COMPANY_MENTIONS, new_mentions)
        updated += 1
        time.sleep(0.3)  # stay within Sheets API rate limits

    print(f"Updated {updated} rows ({skipped} already had company data, skipped).")


if __name__ == "__main__":
    main()
