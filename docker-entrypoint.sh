#!/bin/sh
# Wird vor jedem Container-Start ausgeführt. `flask init-db` ist idempotent
# (wendet ausstehende Alembic-Migrationen an, Daten bleiben erhalten) – damit funktioniert
# der Container sowohl beim erstmaligen Start als auch nach Updates ohne
# manuellen Init-Schritt.
set -e

flask --app app init-db

exec "$@"
