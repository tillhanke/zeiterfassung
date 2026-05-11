#!/usr/bin/env bash
# Installiert die Zeiterfassung als systemd-Service.
# - legt System-User "zeiterfassung" an
# - erstellt Virtualenv und installiert Abhängigkeiten (inkl. gunicorn)
# - generiert /etc/zeiterfassung.env mit einem zufälligen SECRET_KEY
# - rendert deploy/zeiterfassung.service nach /etc/systemd/system/
# - aktiviert + startet den Service
#
# Erneutes Ausführen ist idempotent.
set -euo pipefail

UNIT_NAME="zeiterfassung.service"
SERVICE_USER="zeiterfassung"
ENV_FILE="/etc/zeiterfassung.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_ROOT="${ZEITERF_ROOT:-${APP_ROOT}}"
SRC_UNIT="${SCRIPT_DIR}/${UNIT_NAME}"
DST_UNIT="/etc/systemd/system/${UNIT_NAME}"
VENV="${APP_ROOT}/.venv"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Run as root, e.g.: sudo $0" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found in PATH" >&2
    exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "python3 venv module missing (e.g. Debian: apt install python3-venv)" >&2
    exit 1
fi

if [[ ! -f "${APP_ROOT}/app.py" ]] || [[ ! -f "${SRC_UNIT}" ]]; then
    echo "Expected app at ${APP_ROOT} and unit template at ${SRC_UNIT}" >&2
    exit 1
fi

# System-User anlegen (nologin, kein Home).
if ! id "${SERVICE_USER}" &>/dev/null; then
    useradd --system --user-group --home /nonexistent \
            --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

# Virtualenv + Abhängigkeiten (gunicorn kommt aus requirements.txt).
if [[ ! -x "${VENV}/bin/python" ]]; then
    python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install -r "${APP_ROOT}/requirements.txt"

# Instance-Verzeichnis vorbereiten (einziger schreibbarer Pfad für den Service).
mkdir -p "${APP_ROOT}/instance"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${VENV}" "${APP_ROOT}/instance"

# SECRET_KEY-Datei einmalig erzeugen; bei Re-Install bestehende beibehalten.
if [[ ! -f "${ENV_FILE}" ]]; then
    SECRET_KEY_VALUE="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    umask 077
    cat >"${ENV_FILE}" <<EOF
# Wird von systemd via EnvironmentFile= in den Service injiziert.
# Auto-generiert beim Install. NICHT versionieren.
SECRET_KEY=${SECRET_KEY_VALUE}
EOF
    chown "root:${SERVICE_USER}" "${ENV_FILE}"
    chmod 0640 "${ENV_FILE}"
    echo "Erzeugt: ${ENV_FILE} (zufälliger SECRET_KEY)."
else
    echo "Behalten:  ${ENV_FILE} (existiert bereits)."
fi

# Einmalige DB-Initialisierung als Service-User.
runuser -u "${SERVICE_USER}" -- bash -c "cd '${APP_ROOT}' && '${VENV}/bin/flask' --app app init-db"

# systemd-Unit rendern (sed mit | als Delimiter, daher dürfen Pfade kein | enthalten).
case "${APP_ROOT}${VENV}" in
    *"|"*) echo "APP_ROOT/VENV enthält '|' – bitte umbenennen." >&2; exit 1 ;;
esac
sed \
    -e "s|@APP_ROOT@|${APP_ROOT}|g" \
    -e "s|@VENV@|${VENV}|g" \
    "${SRC_UNIT}" >"${DST_UNIT}"
chmod 0644 "${DST_UNIT}"

systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}"

echo "Installed ${DST_UNIT}, enabled on boot, listening on port 80 as user ${SERVICE_USER}."
echo "App directory:  ${APP_ROOT}"
echo "Virtualenv:     ${VENV}"
echo "Environment:    ${ENV_FILE}"

systemctl --no-pager --full status "${UNIT_NAME}" || true
