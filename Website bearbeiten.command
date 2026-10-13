#!/bin/bash
# Doppelklick startet den Bearbeitungsmodus der Website und öffnet ihn im Browser.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python fehlt auf diesem Rechner. Bitte einmal einrichten lassen (siehe README, Abschnitt Einrichtung)."
  read -r -p "Eingabetaste zum Schließen …"
  exit 1
fi
exec python3 admin/server.py "$@"
