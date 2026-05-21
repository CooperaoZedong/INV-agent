from __future__ import annotations

import os
import anyio
from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Header

from .parser import normalize_agent_output, build_llm_messages
from .schemas import RunResponse, RunRequest
from .store import RUN_STORE, JsonChatStateStore
from src.agent.index import run_agent
from src.integrations.tg_bot import TelegramBotClient
from src.integrations.tg_parser import chunk_text, extract_message, extract_text_message


app = FastAPI(title="Pomoika Agent API")
router = APIRouter(prefix="/telegram", tags=["telegram"])
app.include_router(router)
bot = TelegramBotClient(os.environ.get("TG_BOT_TOKEN"))
state_store = JsonChatStateStore()


def handle_user_message(message: str, source):
    state = state_store.load()

    llm_messages = build_llm_messages(
        state=state,
        user_message=message,
        system_prompt=None,   # already defined in create_agent(...)
        max_recent_turns=5,
    )

    raw_output = run_agent(llm_messages)
    normalized = normalize_agent_output(message, raw_output)

    state_store.append_message("user", message, source)
    state_store.append_message("assistant", normalized.final_answer, "system")

    RUN_STORE[normalized.run_id] = normalized
    return normalized

async def process_telegram_message(chat_id: int, text: str) -> None:
    result = await anyio.to_thread.run_sync(
        lambda: handle_user_message(text, source="telegram")
    )
    reply = result["final_answer"]
    for chunk in chunk_text(reply):
        await bot.send_message(chat_id, chunk)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/runs", response_model=RunResponse)
async def post_run(payload: RunRequest):
    return handle_user_message(payload.prompt, source="streamlit")


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = RUN_STORE[run_id]
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/webhook")
async def telegram_webhook(
        update: dict,
        background_tasks: BackgroundTasks,
        x_telegram_bot_api_secret_token: str | None = Header(
            default=None,
            alias="X-Telegram-Bot-Api-Secret-Token",
        ),
) -> dict:
    if x_telegram_bot_api_secret_token != os.environ.get("TG_BOT_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    msg = extract_message(update)
    if not msg:
        return {"ok": True}

    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    text = (msg.get("text") or "").strip()

    if not chat_id:
        return {"ok": True}

    # Safer v1: private chats only
    if chat_type != "private":
        return {"ok": True}

    if not text:
        await bot.send_message(chat_id, "Please send a text message.")
        return {"ok": True}

    if text == "/start":
        state_store.update_pinned_context(telegram_chat_id=chat_id)
        await bot.send_message(
            chat_id,
            "Connected. You can now ask me to investigate issues from Telegram.",
        )
        return {"ok": True}

    if text == "/reset":
        state_store.reset()
        await bot.send_message(chat_id, "Main chat state has been reset.")
        return {"ok": True}

    if text == "/status":
        state = state_store.load()
        summary = state.summary or "No summary yet."
        await bot.send_message(chat_id, f"Current summary:\n\n{summary[:3000]}")
        return {"ok": True}

    await bot.send_message(chat_id, "Investigating...")

    background_tasks.add_task(process_telegram_message, chat_id, text)
    return {"ok": True}


@router.post("/setup")
async def telegram_setup() -> dict:
    webhook_url = f"{os.environ.get("PUBLIC_BASE_URL")}/telegram/webhook"

    webhook_result = await bot.set_webhook(
        url=webhook_url,
        secret_token=os.environ.get("TG_BOT_TOKEN"),
        allowed_updates=["message"],
        drop_pending_updates=False,
    )

    commands_result = await bot.set_my_commands(
        [
            {"command": "start", "description": "Connect this bot to the main chat"},
            {"command": "status", "description": "Show current conversation summary"},
            {"command": "reset", "description": "Reset the main chat state"},
        ]
    )

    return {
        "webhook": webhook_result,
        "commands": commands_result,
    }