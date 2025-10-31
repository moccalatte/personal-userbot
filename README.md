# Personal Userbot - Keyword Watcher 📡

Userbot ringan buat kebutuhan pribadi: pantau chat/grup tertentu, cari pesan dengan keyword yang kamu tentukan, lalu otomatis catat ke Google Sheets (termasuk username, isi pesan, timestamp, dsb). Tidak butuh Wizard Bot – cukup jalankan userbot langsung dari akun Telegram kamu.

---

## 🚀 Fitur Utama

- 👀 **Watcher**: Monitor beberapa grup sekaligus.
- 🧠 **Flexible Rules**: Bisa `include_all`, `include_any`, dan `exclude` keyword.
- 🗂️ **Multi Rule**: Set label berbeda per rule, cocok untuk berbagai kategori.
- 📝 **Google Sheets Logging**: Simpan data ke spreadsheet (timestamp UTC & lokal, chat name, user, pesan, link).
- 🧾 **Auto Sheet Setup**: Spreadsheet + header dibuat otomatis saat pertama kali jalan.
- ⚙️ **Config interaktif + .env**: Tambah rule langsung dari chat tanpa ubah kode.
- 🪶 **Lightweight**: Cuma pakai Telethon + gspread, jalan di virtualenv biasa.

---

## 📦 Struktur Folder

```
personal-userbot/
├── .env.example                # Template environment kamu
├── requirements.txt
├── README.md
├── scripts/
│   ├── setup.sh                # Buat virtualenv + install dependency
│   └── run.sh                  # Jalankan userbot (aktifkan venv otomatis)
└── src/personal_userbot/
    ├── __init__.py
    ├── config.py               # Loader environment
    ├── rules.py                # Rule manager (JSON storage + evaluator)
    ├── sheets_logger.py        # Helper kirim data ke Google Sheets
    └── runner.py               # Entry point utama
```

---

## 🛠️ Persiapan Awal

1. **Clone Repo / Masuk Folder**
   ```bash
   cd personal-userbot
   ```

2. **Siapkan Virtualenv**
   ```bash
   bash scripts/setup.sh
   # Aktifkan
   source .venv/bin/activate
   ```

3. **Bikin `.env`**
   ```bash
   cp .env.example .env
   ```
   Isi variabel berikut:

   | Variabel | Keterangan |
   |----------|------------|
   | `API_ID`, `API_HASH` | Dari https://my.telegram.org (perlu login) |
   | `STRING_SESSION` | String session Telethon (gunakan script Telethon untuk generate sekali saja) |
   | `WATCH_RULES_FILE` | Lokasi file JSON rules (default `watch_rules.json`, otomatis dibuat) |
   | `WATCH_CHAT_IDS` | Opsional: batasi chat ID (pisahkan koma, gunakan ID negatif untuk grup) |
   | `GOOGLE_SERVICE_ACCOUNT_FILE` | Path ke JSON service account Google |
   | `GOOGLE_SHEETS_SPREADSHEET_ID` | Opsional: ID spreadsheet existing. Kosongkan untuk auto-create |
   | `GOOGLE_SHEETS_SPREADSHEET_TITLE` | Judul spreadsheet baru (default `Personal Watcher Logs`) |
   | `GOOGLE_SHEETS_WORKSHEET` | Nama sheet/tab (default `Sheet1`) |
   | `WATCHER_STATE_FILE` | File lokal untuk menyimpan state (default `watcher_state.json`) |
   | `LOG_LEVEL` | Level log (default `INFO`) |
   | `LOG_FILE` | Path file log rotasi (kosongkan untuk menonaktifkan, default `logs/personal-userbot.log`) |
   | `LOG_MAX_BYTES` | Batas ukuran file log sebelum rotasi (default `1048576` ≈ 1 MB) |
   | `LOG_BACKUP_COUNT` | Jumlah arsip log yang disimpan (default `5`) |
   | `LOCAL_TIMEZONE` | Opsional, contoh `Asia/Jakarta` |
   | `IGNORE_SELF_MESSAGES` | Default `true`, kalau `false` catat juga pesan kamu sendiri |
   | `IGNORE_BOT_MESSAGES` | Default `true`, kalau `false` catat pesan dari akun bot |

   > **Tips**: Buat folder `credentials/` lalu simpan file JSON service account di sana.

4. **Generate STRING_SESSION**  
   Aktifkan virtualenv, kemudian jalankan:
   ```bash
   source .venv/bin/activate
   python scripts/generate_string_session.py
   ```
   Masukkan `API_ID` & `API_HASH`, lalu ikuti instruksi di terminal (kode OTP / 2FA). Salin output yang dihasilkan ke variabel `STRING_SESSION` di `.env`.

5. **Kenali Cara Tambah Rule**  
   Tidak perlu menyalin file contoh. Setelah userbot berjalan, kirim perintah berikut **hanya dari Saved Messages (chat dengan diri sendiri)**:
   ```text
   !watch <chat_id>
   ```
   Bot akan menuntun kamu menjawab pertanyaan (label, keyword `include_all` / `include_any`, dan `exclude`).  
   Setelah langkah selesai, rule otomatis tersimpan ke `watch_rules.json`.

   > ❗️ Demi keamanan, userbot tidak akan mengirim balasan apa pun di grup. Jika kamu mengetik `!watch` di grup, bot akan mengingatkanmu via Saved Messages untuk menjalankannya di sana.

---

## 🔐 Google Sheets Setup (Service Account)

1. Buat project di [Google Cloud Console](https://console.cloud.google.com/).
2. Aktifkan Google Sheets API & Drive API.
3. Buat **Service Account**, generate key JSON → simpan contoh di `credentials/service_account.json`.
4. Buka spreadsheet target → **Share** ke email service account tadi (beri akses Editor).
5. Isi `.env` dengan `GOOGLE_SERVICE_ACCOUNT_FILE`. Biarkan `GOOGLE_SHEETS_SPREADSHEET_ID` kosong bila ingin bot membuat spreadsheet baru otomatis.
6. Jika spreadsheet dibuat otomatis, periksa URL yang dicetak di terminal lalu buka di browser dan bagikan ke akun Google utama kamu supaya bisa diakses.

---

## ▶️ Menjalankan Userbot

```bash
# Pastikan sudah di folder personal-userbot
bash scripts/run.sh
```

Script akan:
- Aktifkan virtualenv (`.venv`)
- Load `.env` dan file rules JSON (akan dibuat otomatis jika belum ada)
- Start Telethon client
- Tulis log ke Google Sheets ketika rule match

> Matikan dengan `Ctrl + C`. Script akan otomatis berhenti dan tampil pesan log.

---

## 📄 Logging & Monitoring

- Secara default bot menulis log ke terminal **dan** file rotasi `logs/personal-userbot.log`. Gunakan `tail -f logs/personal-userbot.log` untuk memantau real-time.
- Sesuaikan path/ukuran/rotasi lewat variabel `LOG_FILE`, `LOG_MAX_BYTES`, dan `LOG_BACKUP_COUNT`. Kosongkan `LOG_FILE` jika hanya ingin output ke terminal/journal.
- Saat dijalankan via `systemd`, log juga masuk ke `journalctl`, contoh: `sudo journalctl -u personal-userbot.service -f`.
- Jika folder `logs/` belum ada, bot akan membuatnya otomatis ketika pertama kali menulis log.

---

## ♻️ Autostart Lewat systemd

Supaya bot otomatis jalan setelah reboot:

1. **Siapkan virtualenv & .env** – pastikan langkah persiapan di atas sudah selesai dan `scripts/run.sh` berjalan normal.
2. **Salin service file contoh**  
   ```bash
   sudo cp systemd/personal-userbot.service /etc/systemd/system/personal-userbot.service
   ```
3. **Edit field spesifik mesin** – ganti `User`, `WorkingDirectory`, `Environment`, `EnvironmentFile`, dan `ExecStart` di `/etc/systemd/system/personal-userbot.service` agar menunjuk ke user serta folder instalasi kamu.  
   - `WorkingDirectory` harus ke root repo (`/home/<user>/.../personal-userbot`).  
   - Pastikan path `.venv/bin/python` sesuai.  
   - Opsional: tambahkan baris `Environment="LOG_FILE=/var/log/personal-userbot.log"` jika ingin menyimpan log ke folder sistem (buat folder & set permission terlebih dulu).
4. **Reload & enable service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now personal-userbot.service
   ```
   Setelah aktif, service akan otomatis start tiap boot.
5. **Cek status & log**
   ```bash
   sudo systemctl status personal-userbot.service
   sudo journalctl -u personal-userbot.service -f
   ```
   6. **Update kode/konfigurasi** – setelah pull perubahan repo atau ubah `.env`, jalankan `sudo systemctl restart personal-userbot.service`.

> Simpan `.env` dengan permission ketat (`chmod 600 .env`) karena berisi STRING_SESSION dan credential lain.

---

## 🧪 Uji Coba Cepat

1. Jalankan `bash scripts/run.sh`.
2. Di Telegram, kirim `!watch <chat_id>` dari Saved Messages lalu ikuti pertanyaannya.
3. Setelah rule tersimpan, kirim pesan yang mengandung keyword ke chat target.
4. Periksa Google Sheets (link dicetak saat awal run): baris baru harus muncul (cek timestamp, label, message).

---

## ❓ FAQ Singkat

- **Dari mana dapatkan chat ID?**  
  Gunakan bot @userinfobot atau aktifkan mode debug Telethon.

- **String session bagaimana caranya?**  
  Jalankan script Telethon resmi:
  ```python
  from telethon import TelegramClient
  from telethon.sessions import StringSession

  api_id = 123456
  api_hash = "xxx"

  with TelegramClient(StringSession(), api_id, api_hash) as client:
      print(client.session.save())
  ```

- **Apakah bot bisa catat pesan lama?**  
  Saat ini hanya memantau pesan baru yang masuk setelah bot berjalan (streaming real-time).

- **Bisa log ke file lokal juga?**  
  Iya, cukup atur `LOG_FILE` (default sudah aktif). Untuk format/custom logging lebih lanjut, modifikasi `configure_logging` di `runner.py`.

---

## 🧹 Tips Maintenance

- Update dependency: `source .venv/bin/activate && pip install -U -r requirements.txt`
- Rotasi credential service account jika ganti project.
- Rutin cek Google Sheets supaya tidak penuh (row limit per sheet ~5 juta).

---

Happy hacking! 🎯 Jika mau tambah fitur (misal kirim notifikasi Telegram), tinggal extend handler di `runner.py`. Struktur sudah modular supaya gampang dikembangkan. Selamat mencoba! 🙌
