#!/bin/bash
# Lance le dashboard « Mon Claude » et l'ouvre dans le navigateur.
# Usage : ./lancer.sh          (ou double-clic depuis le Finder après « chmod +x lancer.sh »)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${DASHBOARD_PORT:-8765}"
DONNEES="${DASHBOARD_DATA:-$HOME/.dashboard-claude}"
URL="http://127.0.0.1:$PORT/"
mkdir -p "$DONNEES"

# 1. Environnement Python isolé (créé une seule fois)
if [ ! -x .venv/bin/python ]; then
  PY=$(./verifier.sh --python) || exit 1
  "$PY" -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

# 2. Serveur (s'il ne tourne pas déjà)
if ! curl -s -m 2 "$URL/api/sante" >/dev/null; then
  nohup .venv/bin/python -m app.serveur >>"$DONNEES/serveur.log" 2>&1 &
  for _ in $(seq 1 30); do curl -s -m 1 "$URL/api/sante" >/dev/null && break; sleep 0.3; done
fi

curl -s -m 2 "$URL/api/sante" >/dev/null || { echo "Le serveur n'a pas démarré. Journal : $DONNEES/serveur.log"; exit 1; }
open "$URL"
echo "Mon Claude est ouvert : $URL  (arrêter : kill \$(lsof -ti tcp:$PORT))"
