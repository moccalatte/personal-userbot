"""Entry point for the personal watcher userbot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Set

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.utils import get_display_name

from .config import ConfigError, Settings, load_settings
from .rules import Rule, RuleRepository, RuleSet
from .sheets_logger import GoogleSheetLogger, MessageRecord

logger = logging.getLogger(__name__)


@dataclass
class PendingRuleSession:
    origin_chat_id: int
    requested_by: int
    target_chat_id: int
    step: str = "label"
    label: Optional[str] = None
    include_all: List[str] = field(default_factory=list)
    include_any: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


def configure_logging(
    level: str,
    log_file: Optional[Path],
    max_bytes: int,
    backup_count: int,
) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    handlers: List[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max(max_bytes, 1_024),
                backupCount=max(0, backup_count),
                encoding="utf-8",
                delay=True,
            )
            handlers.append(file_handler)
        except OSError as exc:
            print(
                f"⚠️  Tidak dapat membuat file log '{log_file}': {exc}",
                file=sys.stderr,
            )

    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _load_state_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Gagal membaca state file '%s': %s", path, exc)
        return {}
    if isinstance(data, dict):
        return data
    logger.warning(
        "Isi state file '%s' tidak valid. Mengabaikan isinya.",
        path,
    )
    return {}


def _save_state_file(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Tidak dapat menulis state file '%s': %s", path, exc)


def _build_message_link(chat_id: int, message_id: int) -> Optional[str]:
    if chat_id >= 0:
        return None  # private chat, cannot build public link
    if str(chat_id).startswith("-100"):
        channel_id = str(chat_id)[4:]
    else:
        channel_id = str(chat_id)[1:]
    return f"https://t.me/c/{channel_id}/{message_id}"


def _matched_keywords(rule: Rule, text: str) -> Sequence[str]:
    normalized = text.casefold()
    found = []
    for keyword in list(rule.include_all) + list(rule.include_any):
        if keyword.casefold() in normalized:
            found.append(keyword)
    return found


async def run(settings: Settings) -> None:
    configure_logging(
        settings.log_level,
        settings.log_file,
        settings.log_max_bytes,
        settings.log_backup_count,
    )

    rule_repo = RuleRepository(settings.rules_file)
    rule_set: RuleSet = rule_repo.ruleset

    manual_chat_filter: Optional[Set[int]] = (
        set(settings.watch_chat_ids) if settings.watch_chat_ids else None
    )

    client = TelegramClient(
        StringSession(settings.string_session), settings.api_id, settings.api_hash
    )

    state = _load_state_file(settings.state_file)
    active_spreadsheet_id = settings.spreadsheet_id or state.get("spreadsheet_id")

    sheet_logger = GoogleSheetLogger(
        service_account_file=str(settings.google_service_account_file),
        spreadsheet_id=active_spreadsheet_id,
        worksheet_name=settings.worksheet_name,
        spreadsheet_title=settings.spreadsheet_title,
    )

    if (
        sheet_logger.spreadsheet_id != active_spreadsheet_id
        or state.get("worksheet_name") != settings.worksheet_name
    ):
        state.update(
            {
                "spreadsheet_id": sheet_logger.spreadsheet_id,
                "worksheet_name": settings.worksheet_name,
                "spreadsheet_title": settings.spreadsheet_title,
            }
        )
        _save_state_file(settings.state_file, state)
        logger.info(
            "Spreadsheet siap digunakan: https://docs.google.com/spreadsheets/d/%s",
            sheet_logger.spreadsheet_id,
        )
    else:
        logger.info(
            "Menggunakan spreadsheet: https://docs.google.com/spreadsheets/d/%s",
            sheet_logger.spreadsheet_id,
        )

    try:
        timezone = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Timezone '%s' tidak ditemukan. Menggunakan UTC.",
            settings.timezone,
        )
        timezone = ZoneInfo("UTC")

    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "String session tidak valid atau belum login. "
            "Gunakan Telethon untuk membuat STRING_SESSION terlebih dahulu."
        )

    logger.info("Personal watcher userbot started.")
    if manual_chat_filter:
        logger.info(
            "Listening on chats (WATCH_CHAT_IDS): %s",
            sorted(manual_chat_filter),
        )
    elif rule_set.chat_ids:
        logger.info(
            "Listening on chats dari rules yang ada: %s",
            sorted(rule_set.chat_ids),
        )
    else:
        logger.info("Listening on all accessible chats.")

    pending_sessions: Dict[int, PendingRuleSession] = {}

    def _parse_keywords(raw: str) -> List[str]:
        cleaned = raw.strip()
        if not cleaned:
            return []
        if cleaned.lower() in {"-", "skip", "none"}:
            return []
        return [
            part.strip()
            for part in re.split(r"[,\n;]+", cleaned)
            if part.strip()
        ]

    def _fmt_keywords(keywords: Sequence[str]) -> str:
        return ", ".join(keywords) if keywords else "-"

    @client.on(events.NewMessage())
    async def handler(event: events.NewMessage.Event) -> None:
        message = event.message
        if not message or not message.text:
            return

        chat_id = event.chat_id if event.chat_id is not None else 0
        text = message.text.strip()
        session = pending_sessions.get(chat_id)
        is_saved_messages = (
            message.sender_id is not None and chat_id == message.sender_id
        )

        if message.out and not is_saved_messages:
            if re.match(r"^!watch\s+(-?\d+)", text, flags=re.IGNORECASE):
                await event.client.send_message(
                    "me",
                    "Perintah !watch hanya boleh dijalankan dari Saved Messages (chat dengan diri sendiri)."
                    " Kirim ulang perintah di sana.",
                )
            return

        if message.out and session and text.lower() == "!cancel":
            pending_sessions.pop(chat_id, None)
            await event.respond("Setup watcher dibatalkan.")
            return

        if message.out:
            match = re.match(r"^!watch\s+(-?\d+)", text, flags=re.IGNORECASE)
            if match:
                target_chat_id = int(match.group(1))
                if session:
                    await event.respond(
                        "Setup watcher sebelumnya digantikan dengan permintaan baru."
                    )
                session = PendingRuleSession(
                    origin_chat_id=chat_id,
                    requested_by=message.sender_id or 0,
                    target_chat_id=target_chat_id,
                )
                pending_sessions[chat_id] = session
                note = ""
                if manual_chat_filter and target_chat_id not in manual_chat_filter:
                    note = (
                        "\nCatatan: chat ini belum ada di WATCH_CHAT_IDS, "
                        "perbarui variabel tersebut agar pesan ikut dipantau."
                    )
                await event.respond(
                    f"Mulai konfigurasi watcher untuk chat {target_chat_id}.\n"
                    "Langkah 1 dari 4 — kirim label rule (misal: Promo Gadget).\n"
                    "Ketik `!cancel` kapan saja untuk batal."
                    + note
                )
                return

        if message.out and session:
            if session.step == "label":
                label = text
                if not label:
                    await event.respond("Label tidak boleh kosong. Coba kirim lagi.")
                    return
                session.label = label
                session.step = "include_all"
                await event.respond(
                    "Langkah 2 dari 4 — sebutkan keyword wajib (include_all).\n"
                    "Pisahkan dengan koma atau baris baru. Kirim '-' jika tidak ada."
                )
                return

            if session.step == "include_all":
                session.include_all = _parse_keywords(text)
                session.step = "include_any"
                prompt = (
                    "Langkah 3 dari 4 — keyword opsional (include_any).\n"
                    "Pisahkan dengan koma atau baris baru. Kirim '-' jika tidak ada."
                )
                if not session.include_all:
                    prompt += (
                        "\nCatatan: karena belum ada include_all, "
                        "minimal satu keyword harus diisi di langkah ini."
                    )
                await event.respond(prompt)
                return

            if session.step == "include_any":
                keywords = _parse_keywords(text)
                if not keywords and not session.include_all:
                    await event.respond(
                        "Minimal harus ada satu keyword. Masukkan keyword include_any "
                        "dipisahkan koma."
                    )
                    return
                session.include_any = keywords
                session.step = "exclude"
                await event.respond(
                    "Langkah 4 dari 4 — keyword pengecualian (exclude).\n"
                    "Pisahkan dengan koma atau kirim '-' jika tidak ada."
                )
                return

            if session.step == "exclude":
                session.exclude = _parse_keywords(text)
                new_rule = Rule(
                    label=session.label or "",
                    include_all=session.include_all,
                    include_any=session.include_any,
                    exclude=session.exclude,
                    chat_ids={session.target_chat_id},
                )
                rule_repo.add_rule(new_rule)
                pending_sessions.pop(chat_id, None)
                logger.info(
                    "Rule baru ditambahkan: label='%s' target_chat=%s",
                    new_rule.label,
                    session.target_chat_id,
                )
                summary_lines = [
                    f"Watcher baru tersimpan untuk chat {session.target_chat_id}:",
                    f"- Label: {new_rule.label}",
                    f"- include_all: {_fmt_keywords(new_rule.include_all)}",
                    f"- include_any: {_fmt_keywords(new_rule.include_any)}",
                    f"- exclude: {_fmt_keywords(new_rule.exclude)}",
                ]
                if manual_chat_filter and session.target_chat_id not in manual_chat_filter:
                    summary_lines.append(
                        "- Catatan: chat ini belum ada di WATCH_CHAT_IDS, "
                        "perbarui env bila ingin dipantau."
                    )
                await event.respond("\n".join(summary_lines))
                return

        if manual_chat_filter and chat_id not in manual_chat_filter:
            return

        rule_chat_filter = rule_set.chat_ids
        if rule_chat_filter is not None and chat_id not in rule_chat_filter:
            return

        if settings.ignore_self_messages and message.out:
            return

        if (
            settings.ignore_bot_messages
            and message.sender
            and getattr(message.sender, "bot", False)
        ):
            return

        matches = rule_set.match(chat_id, message.text)
        if not matches:
            return

        chat = await event.get_chat()

        username = (
            message.sender.username if message.sender and message.sender.username else None
        )
        display_name = (
            get_display_name(message.sender) if message.sender else None
        )
        telegram_id = message.sender_id
        chat_name = get_display_name(chat)
        link = _build_message_link(chat_id, message.id)
        timestamp_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
        timestamp_local = timestamp_utc.astimezone(timezone)

        for rule in matches:
            record = MessageRecord(
                label=rule.label,
                chat_id=chat_id,
                chat_name=chat_name,
                username=username,
                display_name=display_name,
                telegram_id=telegram_id,
                message_id=message.id,
                message_text=message.text,
                message_link=link,
                matched_keywords=_matched_keywords(rule, message.text),
                excluded_keywords=list(rule.exclude),
                timestamp_utc=timestamp_utc,
                timestamp_local=timestamp_local,
            )
            try:
                await sheet_logger.append(record)
                logger.info(
                    "Logged message %s dari %s rule='%s'",
                    message.id,
                    chat_name,
                    rule.label,
                )
            except Exception as exc:  # pragma: no cover - external API
                logger.exception(
                    "Gagal menulis ke Google Sheets untuk message %s: %s",
                    message.id,
                    exc,
                )

    await client.run_until_disconnected()


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    env_path = root_dir / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    load_dotenv(override=False)  # fallback to local .env in cwd

    try:
        settings = load_settings()
    except ConfigError as exc:
        raise SystemExit(f"❌ Konfigurasi tidak valid: {exc}") from exc

    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        logger.info("Userbot dihentikan melalui keyboard interrupt.")


if __name__ == "__main__":
    main()
