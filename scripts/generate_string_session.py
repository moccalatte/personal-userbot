#!/usr/bin/env python3
"""Utility script to generate Telethon STRING_SESSION interactively."""

from __future__ import annotations

import getpass
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession


def prompt_api_id() -> int:
    while True:
        raw = input("Masukkan API_ID (numerik): ").strip()
        if not raw:
            print("API_ID tidak boleh kosong.", file=sys.stderr)
            continue
        try:
            return int(raw)
        except ValueError:
            print("API_ID harus berupa angka. Coba lagi.", file=sys.stderr)


def prompt_api_hash() -> str:
    while True:
        raw = getpass.getpass("Masukkan API_HASH: ").strip()
        if not raw:
            print("API_HASH tidak boleh kosong.", file=sys.stderr)
            continue
        return raw


def main() -> None:
    print("=== Generator STRING_SESSION Telethon ===")
    print("Pastikan API ID & API HASH dari https://my.telegram.org/apps.")
    print("Kode OTP dan, bila perlu, password 2FA akan diminta di terminal.\n")

    api_id = prompt_api_id()
    api_hash = prompt_api_hash()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session = client.session.save()

    print("\n=== STRING_SESSION Berhasil Dibuat ===")
    print("Salin seluruh teks di bawah dan simpan ke variabel STRING_SESSION pada .env:\n")
    print(session)
    print("\nSimpan kredensial ini dengan aman. Jangan bagikan ke orang lain.")


if __name__ == "__main__":
    main()
