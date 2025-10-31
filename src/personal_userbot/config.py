"""Configuration handling for the personal watcher userbot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set
import os


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    api_id: int
    api_hash: str
    string_session: str
    rules_file: Path
    google_service_account_file: Path
    spreadsheet_id: Optional[str]
    spreadsheet_title: str
    worksheet_name: str
    watch_chat_ids: Optional[Set[int]]
    log_level: str
    log_file: Optional[Path]
    log_max_bytes: int
    log_backup_count: int
    timezone: str
    ignore_self_messages: bool
    ignore_bot_messages: bool
    state_file: Path


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Environment variable '{name}' is required.")
    return value


def _parse_chat_ids(raw: str | None) -> Optional[Set[int]]:
    if not raw:
        return None
    chat_ids: Set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            chat_ids.add(int(chunk))
        except ValueError as exc:  # pragma: no cover - configuration guard
            raise ConfigError(
                f"Invalid chat id '{chunk}' in WATCH_CHAT_IDS. Use integers."
            ) from exc
    return chat_ids or None


def _parse_positive_int(
    name: str,
    default: int,
    minimum: int = 1,
) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} harus berupa angka bulat.") from exc
    if value < minimum:
        raise ConfigError(f"{name} harus lebih besar atau sama dengan {minimum}.")
    return value


def load_settings() -> Settings:
    """Load settings from environment variables."""

    api_id_raw = _require_env("API_ID")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise ConfigError("API_ID must be an integer.") from exc

    rules_file = Path(
        os.getenv("WATCH_RULES_FILE", "watch_rules.json")
    ).expanduser()
    if rules_file.suffix and rules_file.suffix.lower() not in {".json"}:
        raise ConfigError(
            f"WATCH_RULES_FILE '{rules_file}' harus menggunakan ekstensi .json."
        )

    service_account_path = Path(
        _require_env("GOOGLE_SERVICE_ACCOUNT_FILE")
    ).expanduser()
    if not service_account_path.exists():
        raise ConfigError(
            f"Google service account file '{service_account_path}' not found."
        )

    raw_spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    spreadsheet_id = raw_spreadsheet_id.strip() if raw_spreadsheet_id else None
    spreadsheet_title = (
        os.getenv("GOOGLE_SHEETS_SPREADSHEET_TITLE", "Personal Watcher Logs").strip()
        or "Personal Watcher Logs"
    )
    worksheet_name = (
        os.getenv("GOOGLE_SHEETS_WORKSHEET", "Sheet1").strip() or "Sheet1"
    )
    state_file = Path(
        os.getenv("WATCHER_STATE_FILE", "watcher_state.json")
    ).expanduser()
    log_file_raw = os.getenv("LOG_FILE", "logs/personal-userbot.log").strip()
    log_file = Path(log_file_raw).expanduser() if log_file_raw else None
    log_max_bytes = _parse_positive_int("LOG_MAX_BYTES", default=1_048_576)
    log_backup_count = _parse_positive_int("LOG_BACKUP_COUNT", default=5)

    return Settings(
        api_id=api_id,
        api_hash=_require_env("API_HASH"),
        string_session=_require_env("STRING_SESSION"),
        rules_file=rules_file,
        google_service_account_file=service_account_path,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_title=spreadsheet_title,
        worksheet_name=worksheet_name,
        watch_chat_ids=_parse_chat_ids(os.getenv("WATCH_CHAT_IDS")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_file=log_file,
        log_max_bytes=log_max_bytes,
        log_backup_count=log_backup_count,
        timezone=os.getenv("LOCAL_TIMEZONE", "UTC"),
        ignore_self_messages=os.getenv("IGNORE_SELF_MESSAGES", "true").lower()
        in {"1", "true", "yes", "on"},
        ignore_bot_messages=os.getenv("IGNORE_BOT_MESSAGES", "true").lower()
        in {"1", "true", "yes", "on"},
        state_file=state_file,
    )
