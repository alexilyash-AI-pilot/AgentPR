"""
AgentPR Bot Server — FastAPI webhook powered by OpenAI GPT-4o-mini.

Every Telegram message → POST /webhook → GPT decides tool to call →
search_articles / send_to_group / create_sheet_tab.

Group behaviour: only responds when @ChoicePRbot is mentioned or user
replies directly to the bot's message.

Confirm-before-send: after searching, GPT always asks "Send here or
Google Sheet?" before posting or saving anything.
"""

import json
import logging
import os

import openai
import requests
from fastapi import BackgroundTasks, FastAPI, Request

from tools import create_sheet_tab, search_articles, send_articles_to_group

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory state (resets on redeploy — acceptable for this use case)
# ---------------------------------------------------------------------------
CONVERSATIONS: dict[str, list] = {}   # chat_id → message history
SEARCH_CACHE:  dict[str, dict] = {}   # chat_id → {articles, query}
MAX_HISTORY = 30

BOT_USERNAME = os.environ.get("BOT_USERNAME", "ChoicePRbot")

SYSTEM_PROMPT = (
    "You are AgentPR, a professional PR research assistant for Choice — "
    "a restaurant CRM and loyalty platform operating across Europe (choiceqr.com / choice.app).\n\n"
    "Your job: help the PR team find relevant EU/European news articles about:\n"
    "• Choice (ChoiceQR, choice.app, Czech Choice)\n"
    "• Competitors: Deliverect, Sunday.app, Restimo, Restaumatic, Upmenu\n"
    "• Topics: AI restaurants, restaurant tech, foodtech, restaurant SaaS, hospitality tech\n\n"
    "Rules you MUST follow:\n"
    "1. Only search EU/European sources in English.\n"
    "2. When asked to find articles → call search_articles immediately.\n"
    "3. After search returns results, show a numbered list, then ALWAYS ask:\n"
    "   'Found [N] articles. Where should I send them?\n"
    "   1️⃣  Here in the group\n"
    "   2️⃣  New Google Sheet tab'\n"
    "4. Do NOT call send_to_group or create_sheet_tab until the user replies.\n"
    "5. '1' / 'here' / 'group' / 'send here' → call send_to_group.\n"
    "6. '2' / 'sheet' / 'google sheet' / 'spreadsheet' → call create_sheet_tab.\n"
    "7. If search returns 0 results → tell the user; no need to ask where to send.\n"
    "8. Be concise and professional."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_articles",
            "description": (
                "Search for EU/European news articles in English on a given topic. "
                "Use this whenever the user asks to find, search, or show articles. "
                "After the search, show a numbered summary and ALWAYS ask where to send them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search topic, e.g. 'Deliverect funding Europe', 'AI restaurants'",
                    },
                    "days": {
                        "type": "integer",
                        "description": "How many days back to search. Default 90.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_to_group",
            "description": (
                "Post the previously found articles as Telegram messages in this group. "
                "Only call this after the user explicitly chose option 1 or said "
                "'here', 'group', 'send here', 'post here', or '1'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_sheet_tab",
            "description": (
                "Save the previously found articles to a new tab in the AgentPR Articles "
                "Google Sheet and return the link. "
                "Only call this after the user explicitly chose option 2 or said "
                "'sheet', 'google sheet', 'spreadsheet', or '2'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI()


@app.get("/")
def health():
    return {"status": "ok", "service": "AgentPR Bot", "bot": f"@{BOT_USERNAME}"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Telegram POSTs here for every new message."""
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}
    background_tasks.add_task(_handle_update, data)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Update handler
# ---------------------------------------------------------------------------

def _handle_update(data: dict) -> None:
    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return

    chat_id   = str(msg["chat"]["id"])
    text      = (msg.get("text") or "").strip()
    chat_type = msg["chat"].get("type", "private")

    # Groups: only respond to @mentions or replies to bot
    if chat_type in ("group", "supergroup"):
        mention = f"@{BOT_USERNAME}"
        is_mention = mention in text
        reply_to = msg.get("reply_to_message") or {}
        is_reply_to_bot = (reply_to.get("from") or {}).get("username", "") == BOT_USERNAME
        if not is_mention and not is_reply_to_bot:
            return
        text = text.replace(mention, "").strip()

    if not text:
        return

    logger.info("[%s] %s", chat_id, text[:100])

    history = CONVERSATIONS.get(chat_id, [])
    history.append({"role": "user", "content": text})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    _run_agent(history, chat_id)
    CONVERSATIONS[chat_id] = history


# ---------------------------------------------------------------------------
# OpenAI agentic loop
# ---------------------------------------------------------------------------

def _run_agent(history: list, chat_id: str) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _send(chat_id, "⚠️ OPENAI_API_KEY is not configured.")
        return

    client = openai.OpenAI(api_key=api_key)

    for round_num in range(6):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                tools=TOOLS,
                tool_choice="auto",
            )
        except openai.OpenAIError as exc:
            logger.error("OpenAI error: %s", exc)
            _send(chat_id, "⚠️ AI service error. Please try again.")
            return

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        logger.info("Round %d: finish_reason=%s", round_num, finish_reason)

        if finish_reason == "stop":
            reply = msg.content or ""
            if reply:
                _send(chat_id, reply)
            history.append({"role": "assistant", "content": reply})
            return

        if finish_reason == "tool_calls":
            # Add assistant message with tool_calls to history
            history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in (msg.tool_calls or [])
                ],
            })

            for tc in (msg.tool_calls or []):
                try:
                    inputs = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    inputs = {}

                result = _execute_tool(tc.function.name, inputs, chat_id)
                logger.info("Tool '%s' result: %s", tc.function.name, str(result)[:120])

                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result if isinstance(result, str) else json.dumps(result),
                })
            continue

        logger.warning("Unexpected finish_reason: %s", finish_reason)
        break

    _send(chat_id, "Processing limit reached. Please try again.")


def _execute_tool(name: str, inputs: dict, chat_id: str) -> str:
    if name == "search_articles":
        query    = inputs.get("query", "")
        days     = int(inputs.get("days", 90))
        articles = search_articles(query, days)
        SEARCH_CACHE[chat_id] = {"articles": articles, "query": query}
        if not articles:
            return f"No EU/English articles found for '{query}' in the past {days} days."
        lines = [f"Found {len(articles)} EU articles for '{query}' (past {days} days):"]
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. {a['title']}  |  {a['portal']}  |  {a['published']}")
        return "\n".join(lines)

    if name == "send_to_group":
        cached = SEARCH_CACHE.get(chat_id, {})
        if not cached.get("articles"):
            return "No recent search results found. Please run a search first."
        return send_articles_to_group(cached["articles"], chat_id)

    if name == "create_sheet_tab":
        cached = SEARCH_CACHE.get(chat_id, {})
        if not cached.get("articles"):
            return "No recent search results found. Please run a search first."
        return create_sheet_tab(cached.get("query", "search"), cached["articles"])

    return f"Unknown tool: {name}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send(chat_id: str, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            r = requests.post(
                api,
                json={"chat_id": chat_id, "text": chunk,
                      "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=10,
            )
            if not r.json().get("ok"):
                requests.post(api,
                    json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                    timeout=10)
        except Exception as exc:
            logger.error("_send failed: %s", exc)
