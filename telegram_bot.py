import os
import logging
import time
from email.utils import parsedate_to_datetime
from typing import Optional
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _telegram_disabled() -> bool:
    return os.environ.get("TELEGRAM_DISABLED", "").lower() in ("1", "true", "yes")


def _sheet_link_line() -> str:
    sid = os.environ.get("SPREADSHEET_ID", "").strip()
    if not sid:
        return ""
    url = f"https://docs.google.com/spreadsheets/d/{sid}"
    return f"\n\n📊 Sheet: {url}"


def send_article(article: dict) -> bool:
    """
    Send a single article notification to the configured Telegram group.
    Returns True on success, False on failure.
    """
    if _telegram_disabled():
        logger.info("Telegram disabled (TELEGRAM_DISABLED=1), skipping send.")
        return True

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False

    title = article.get("title", "No title")
    portal = article.get("portal", "—")
    pub_date = _format_date(article.get("published_date", ""))
    url = article.get("url", "")
    description = article.get("description", "").strip()

    # Resolve company mentions: prefer list, fall back to single string
    companies: list[str] = article.get("companies") or []
    if not companies:
        single = article.get("company", "")
        companies = [single] if single else ["Restaurant Tech"]

    # First sentence as the one-line summary
    if description:
        summary = description.split(". ")[0].strip()
        if not summary.endswith("."):
            summary += "."
    else:
        summary = "No summary available."

    company_bullets = "\n".join(f"• {_escape(c)}" for c in companies)

    text = (
        f"📰 <b>{_escape(title)}</b>\n\n"
        f"🏢 Company mentions:\n{company_bullets}\n\n"
        f"📝 Summary:\n{_escape(summary)}\n\n"
        f"🌐 Portal:\n{_escape(portal)}\n\n"
        f"🔗 Link:\n{url}\n\n"
        f"📅 Publication date: {pub_date}"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                TELEGRAM_API.format(token=token),
                json=payload,
                timeout=10,
            )
            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 10)
                logger.warning("Telegram rate limited — waiting %ds before retry.", retry_after)
                time.sleep(retry_after + 1)
                continue
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Telegram send failed for '%s': %s", title, exc)
            if attempt < 2:
                time.sleep(5)
    return False


def send_run_report(
    candidate_new: int,
    dedup_winners: int,
    sent_count: int,
    *,
    note: Optional[str] = None,
) -> None:
    """
    Single end-of-run summary: always sent when Telegram is enabled and configured.

    Covers: no new articles; new candidates but nothing sent (dedup or failures);
    normal runs with per-article sends plus recap counts.
    """
    if _telegram_disabled():
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    sheet = _sheet_link_line()

    if candidate_new == 0:
        text = f"✅ AgentPR scan complete — no new articles found this run.{sheet}"
    elif sent_count == 0:
        text = (
            f"⚠️ Found {candidate_new} candidate article(s) after cross-run dedupe "
            f"but {dedup_winners} after story dedupe; sent 0. "
            f"Check logs / filters.{sheet}"
        )
        if note:
            text += f"\n\n{note}"
    else:
        text = (
            f"✅ AgentPR run complete.\n"
            f"• New candidates (cross-run dedupe): {candidate_new}\n"
            f"• After story dedupe: {dedup_winners}\n"
            f"• Telegram article messages sent: {sent_count}{sheet}"
        )
        if note:
            text += f"\n\n{note}"

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("send_run_report failed: %s", exc)


def send_error(message: str) -> None:
    """Send a monitor failure alert to the configured Telegram group."""
    if _telegram_disabled():
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    text = f"🚨 AgentPR monitor failed\n\n{message[:3500]}"
    try:
        requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except requests.RequestException:
        pass


def _format_author(article: dict) -> str:
    first = article.get("author_first", "")
    last = article.get("author_last", "")
    full = f"{first} {last}".strip()
    return full if full else "Unknown"


def _format_date(date_str: str) -> str:
    """Parse any date format and return YYYY-MM-DD for display."""
    if not date_str:
        return "—"
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        pass
    # Already in YYYY-MM-DD
    if len(date_str) >= 10 and date_str[4] == "-":
        return date_str[:10]
    return date_str[:10] if date_str else "—"


def _escape(text: str) -> str:
    """Minimal HTML escaping for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
