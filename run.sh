#!/usr/bin/env bash
# Startet den Zeiterfassungs-Container mit persistenter Datenbank in
# ./instance. SECRET_KEY MUSS gesetzt sein – in Produktion bitte einen
# echten Zufallswert verwenden (z. B. `python3 -c 'import secrets;
# print(secrets.token_hex(32))'`).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCE_DIR="${SCRIPT_DIR}/instance"
PORT="${PORT:-8000}"

if [[ -z "${SECRET_KEY:-}" ]]; then
    echo "WARN: SECRET_KEY ist nicht gesetzt – verwende Dev-Default. NICHT für Produktion benutzen!" >&2
    SECRET_KEY="dev-secret-key-change-me"
fi

mkdir -p "${INSTANCE_DIR}"

exec docker run --rm \
    -p "${PORT}:8000" \
    -v "${INSTANCE_DIR}:/app/instance" \
    -e "SECRET_KEY=${SECRET_KEY}" \
    --name zeiterfassung \
    zeiterfassung
