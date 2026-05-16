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

    title = article.get("title", "No title")
    portal = article.get("portal", "—")
    pub_date = article.get("published_date", "—")
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
