#!/usr/bin/env bash
# Baut das Docker-Image "zeiterfassung". Init der Datenbank passiert
# automatisch beim Container-Start (siehe docker-entrypoint.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

docker build -t zeiterfassung .
