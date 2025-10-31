"""Google Sheets logging helper."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

HEADERS: Tuple[str, ...] = (
    "timestamp_utc",
    "timestamp_local",
    "rule_label",
    "chat_name",
    "chat_id",
    "message_id",
    "message_link",
    "username",
    "display_name",
    "telegram_user_id",
    "message_text",
    "matched_keywords",
    "excluded_keywords",
)


@dataclass(frozen=True)
class MessageRecord:
    """Normalized message payload sent to Google Sheets."""

    label: str
    chat_id: int
    chat_name: str
    username: str | None
    display_name: str | None
    telegram_id: int | None
    message_id: int
    message_text: str
    message_link: str | None
    matched_keywords: Sequence[str]
    excluded_keywords: Sequence[str]
    timestamp_utc: datetime
    timestamp_local: datetime

    def as_row(self) -> List[Any]:
        """Return the row representation for gspread."""
        return [
            self.timestamp_utc.isoformat(),
            self.timestamp_local.isoformat(),
            self.label,
            self.chat_name,
            self.chat_id,
            self.message_id,
            self.message_link or "",
            self.username or "",
            self.display_name or "",
            self.telegram_id or "",
            self.message_text,
            ", ".join(self.matched_keywords),
            ", ".join(self.excluded_keywords),
        ]


class GoogleSheetLogger:
    """Append structured rows to Google Sheets asynchronously."""

    def __init__(
        self,
        *,
        service_account_file: str,
        spreadsheet_id: Optional[str],
        worksheet_name: str,
        spreadsheet_title: str,
    ) -> None:
        self._service_account_file = service_account_file
        self._worksheet_name = worksheet_name
        self._spreadsheet_title = spreadsheet_title
        self._client = self._authorize(service_account_file)
        (
            self._spreadsheet_id,
            self._worksheet,
        ) = self._connect(spreadsheet_id)

    @staticmethod
    def _authorize(service_account_file: str):
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            service_account_file, scopes=SCOPES
        )
        return gspread.authorize(credentials)

    def _connect(self, spreadsheet_id: Optional[str]) -> Tuple[str, gspread.Worksheet]:
        if spreadsheet_id:
            logger.info(
                "Menyambungkan ke spreadsheet yang sudah ada (%s).", spreadsheet_id
            )
            spreadsheet = self._client.open_by_key(spreadsheet_id)
            created = False
        else:
            logger.info(
                "Spreadsheet ID tidak ditemukan. Membuat spreadsheet baru '%s'.",
                self._spreadsheet_title,
            )
            spreadsheet = self._client.create(self._spreadsheet_title)
            spreadsheet_id = spreadsheet.id
            created = True

        worksheet: gspread.Worksheet
        if created:
            worksheet = spreadsheet.sheet1
            if worksheet.title != self._worksheet_name:
                worksheet.update_title(self._worksheet_name)
        else:
            try:
                worksheet = spreadsheet.worksheet(self._worksheet_name)
            except gspread.WorksheetNotFound:
                logger.info(
                    "Worksheet '%s' tidak ditemukan. Membuat worksheet baru.",
                    self._worksheet_name,
                )
                worksheet = spreadsheet.add_worksheet(
                    title=self._worksheet_name, rows="2000", cols=str(len(HEADERS))
                )
                created = True

        self._ensure_headers(worksheet, new_sheet=created)
        return spreadsheet_id or spreadsheet.id, worksheet

    @property
    def spreadsheet_id(self) -> str:
        return self._spreadsheet_id

    @property
    def worksheet_name(self) -> str:
        return self._worksheet_name

    def _ensure_headers(self, worksheet: gspread.Worksheet, *, new_sheet: bool) -> None:
        try:
            existing = worksheet.row_values(1)
        except gspread.exceptions.APIError as exc:  # pragma: no cover - defensive
            logger.warning("Gagal membaca header worksheet: %s", exc)
            existing = []

        sanitized = [value.strip() for value in existing]
        if sanitized == list(HEADERS):
            return

        if existing and not new_sheet:
            logger.warning(
                "Header worksheet '%s' berbeda dari format yang diharapkan. "
                "Baris pertama tidak diubah untuk menjaga data.",
                worksheet.title,
            )
            return

        logger.info("Menginisialisasi header worksheet '%s'.", worksheet.title)
        worksheet.clear()
        worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")
        try:
            worksheet.freeze(rows=1)
        except gspread.exceptions.APIError:  # pragma: no cover - optional capability
            logger.debug("Tidak dapat melakukan freeze pada header worksheet.")

    async def append(self, record: MessageRecord) -> None:
        """Append a record to the Google Sheet."""

        row = record.as_row()

        def _append():
            logger.debug("Appending row to Google Sheets: %s", row)
            self._worksheet.append_row(row, value_input_option="USER_ENTERED")

        await asyncio.to_thread(_append)
