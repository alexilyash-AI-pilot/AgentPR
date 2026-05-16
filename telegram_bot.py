import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_article(article: dict) -> bool:
    """
    Send a single article notification to the configured Telegram group.
    Returns True on success, False on failure.
    """
    if os.environ.get("TELEGRAM_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("Telegram disabled (TELEGRAM_DISABLED=1), skipping send.")
        return True

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False

    author = _format_author(article)
    company = article.get("company", "—")
    portal = article.get("portal", "—")
    country = article.get("country", "—")
    pub_date = article.get("published_date", "—")
    url = article.get("url", "")
    title = article.get("title", "No title")

    text = (
        f"📰 <b>{_escape(title)}</b>\n"
        f"\n"
        f"🔗 <a href=\"{url}\">{url}</a>\n"
        f"🏢 About: <b>{_escape(company)}</b>\n"
        f"✍️ Editor: {_escape(author)}\n"
        f"🌐 Portal: {_escape(portal)}\n"
        f"🗺 Country: {_escape(country)}\n"
        f"📅 Published: {pub_date}"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("Telegram send failed for '%s': %s", title, exc)
        return False


def send_summary(total_new: int) -> None:
    """Send a brief run-summary message (used when 0 new articles found)."""
    if total_new > 0:
        return  # individual messages already sent

    if os.environ.get("TELEGRAM_DISABLED", "").lower() in ("1", "true", "yes"):
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    text = "✅ AgentPR scan complete — no new articles found this run."
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


def _escape(text: str) -> str:
    """Minimal HTML escaping for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
