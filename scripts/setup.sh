#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"

if [[ ! -x "$(command -v python3)" ]]; then
  echo "Python3 tidak ditemukan. Install Python 3.10+ terlebih dahulu."
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Membuat virtualenv di ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r "${PROJECT_DIR}/requirements.txt"

echo "Virtualenv siap. Gunakan 'source ${VENV_DIR}/bin/activate' sebelum menjalankan bot."
echo "INFO: Untuk membuat STRING_SESSION jalankan setelah aktivasi venv: python scripts/generate_string_session.py"
