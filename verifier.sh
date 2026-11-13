#!/bin/bash
# Vérifie que ce Mac a tout ce qu'il faut pour faire tourner « Mon Claude », et dit quoi faire sinon.
#
#   ./verifier.sh              bilan complet, avec la marche à suivre pour chaque manque
#   ./verifier.sh --silencieux n'affiche que les manques bloquants (utilisé par installer.sh)
#   ./verifier.sh --python     affiche le Python à utiliser (utilisé par installer.sh et lancer.sh)
#
# ✔ prêt · ✘ indispensable manquant (l'installation s'arrête) · ⚠ optionnel (une fonction sera indisponible)
# Ne modifie rien : lecture seule.
set -uo pipefail
cd "$(dirname "$0")"
MODE="${1:-}"
PORT="${DASHBOARD_PORT:-8765}"
MODELE="${DASHBOARD_WHISPER_MODELE:-$HOME/.dashboard-claude/modeles/ggml-large-v3-turbo-q5_0.bin}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
BLOQUANTS=0

ok()   { [ "$MODE" = "--silencieux" ] || printf "  ✔ %s\n" "$1"; }
non()  { BLOQUANTS=$((BLOQUANTS + 1)); printf "  ✘ %s\n" "$1"; [ -n "${2:-}" ] && printf "      → %s\n" "$2"; }
bof()  { [ "$MODE" = "--silencieux" ] && return; printf "  ⚠ %s\n" "$1"; [ -n "${2:-}" ] && printf "      → %s\n" "$2"; }
titre() { [ "$MODE" = "--silencieux" ] || printf "\n%s\n" "$1"; }

# Python 3.10 minimum (bibliothèque Claude Agent SDK) ; testé avec 3.12.
trouver_python() {
  for p in python3.12 python3.13 python3.11 /opt/homebrew/bin/python3.12 python3; do
    local c; c=$(command -v "$p" 2>/dev/null) || continue
    "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && { echo "$c"; return 0; }
  done
  return 1
}

if [ "$MODE" = "--python" ]; then
  trouver_python || { echo "Python 3.10 ou plus introuvable : brew install python@3.12" >&2; exit 1; }
  exit 0
fi

[ "$MODE" = "--silencieux" ] || echo "Mon Claude — vérification de la configuration"

titre "Indispensable"
if [ "$(uname -s)" = "Darwin" ]; then ok "macOS $(sw_vers -productVersion)"
else non "Ce n'est pas un Mac" "Mon Claude ne s'installe pour l'instant que sur macOS."; fi

if PY=$(trouver_python); then ok "Python $("$PY" -c 'import platform; print(platform.python_version())') ($PY)"
else non "Python 3.10 ou plus introuvable" "Installe Homebrew (https://brew.sh), puis : brew install python@3.12"; fi

if CLAUDE=$(command -v claude 2>/dev/null); then
  ok "Claude Code $(claude --version 2>/dev/null | head -1)"
  # « auth status » renvoie du JSON ; on n'en lit que deux champs (jamais l'adresse mail).
  ETAT=$(claude auth status 2>/dev/null | ${PY:-python3} -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    print("inconnu"); sys.exit()
print(("oui" if d.get("loggedIn") else "non") + " " + str(d.get("authMethod") or "?"))' 2>/dev/null || echo "inconnu")
  case "$ETAT" in
    "oui claude.ai") ok "Connecté à ton abonnement Claude (Pro ou Max)";;
    oui\ *) bof "Connecté, mais pas par un abonnement claude.ai (${ETAT#oui })" "Chaque message sera facturé à la clé API. Pour utiliser ton abonnement : claude, puis /login.";;
    non\ *) non "Claude Code n'est pas connecté" "Ouvre le Terminal, tape : claude   puis suis les étapes de connexion (/login).";;
    *) bof "État de connexion illisible (version de Claude Code trop ancienne ?)" "Mets à jour : claude update   puis relance ce bilan.";;
  esac
else
  non "Claude Code introuvable" "Installe-le : https://docs.claude.com/fr/docs/claude-code/setup   puis connecte-toi en tapant : claude"
fi

for outil in curl osacompile launchctl; do
  command -v "$outil" >/dev/null 2>&1 && ok "$outil" || non "$outil introuvable" "Outil fourni avec macOS : vérifie ton installation."
done

if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  sante() { for _ in 1 2 3; do curl -s -m 3 "http://127.0.0.1:$PORT/api/sante" >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }
  if sante; then ok "Port $PORT : Mon Claude tourne déjà (il sera mis à jour)"
  else non "Port $PORT occupé par une autre application" "Choisis un autre port : DASHBOARD_PORT=8780 ./installer.sh"; fi
else ok "Port $PORT libre"; fi

titre "Optionnel"
command -v brew >/dev/null 2>&1 && ok "Homebrew" || bof "Homebrew absent" "Utile pour Python et la dictée : https://brew.sh"
if command -v whisper-cli >/dev/null 2>&1 || [ -x "${DASHBOARD_WHISPER:-/nonexistent}" ]; then
  ok "Dictée : whisper-cli"
  if [ -f "$MODELE" ]; then ok "Dictée : modèle vocal présent"
  else bof "Dictée : modèle vocal absent (~550 Mo)" "mkdir -p ~/.dashboard-claude/modeles && curl -L -o \"$MODELE\" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"; fi
else
  bof "Dictée indisponible : whisper-cli absent" "brew install whisper-cpp   (puis relance ce bilan pour le modèle vocal)"
fi
[ -d "/Applications/Google Chrome.app" ] && ok "Google Chrome (fenêtre dédiée possible)" \
  || bof "Google Chrome absent" "Facultatif : Chrome permet d'ouvrir Mon Claude dans sa propre fenêtre, sans onglets."

if [ "$MODE" != "--silencieux" ]; then
  echo
  if [ "$BLOQUANTS" -eq 0 ]; then echo "Tout l'indispensable est prêt. Étape suivante : ./installer.sh"
  else echo "$BLOQUANTS point(s) indispensable(s) à corriger (✘), puis relance : ./verifier.sh"; fi
fi
[ "$BLOQUANTS" -eq 0 ]
