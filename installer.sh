#!/bin/bash
# Installe « Mon Claude » pour qu'il démarre tout seul à l'ouverture de session et reste lancé.
#
#   ./installer.sh        installe ou met à jour (copie la version actuelle du code)
#   ./installer.sh --retirer   arrête et retire le lancement automatique (les données restent)
#
# Ce que ça crée :
#   ~/.local/share/mon-claude/app     copie du code (jamais le dossier de développement)
#   ~/.local/share/mon-claude/venv    environnement Python isolé
#   ~/Library/LaunchAgents/local.mon-claude.plist   démarrage automatique
#   ~/Applications/Mon Claude.app     raccourci à poser dans le Dock
# Données (réglages, lien iCal, images) : ~/.dashboard-claude — jamais touchées par ce script.
set -euo pipefail
cd "$(dirname "$0")"

ICI="$HOME/.local/share/mon-claude"
ETIQUETTE="local.mon-claude"
ANCIENNE=""   # nom des premières versions : remplacé à la mise à jour
PLIST="$HOME/Library/LaunchAgents/$ETIQUETTE.plist"
PORT="${DASHBOARD_PORT:-8765}"
DOMAINE="gui/$(id -u)"

arreter() {
  launchctl bootout "$DOMAINE/$ETIQUETTE" 2>/dev/null || true
  # bootout est asynchrone : attendre que le service ait vraiment disparu avant de le recharger
  for _ in $(seq 1 20); do launchctl print "$DOMAINE/$ETIQUETTE" >/dev/null 2>&1 || return 0; sleep 0.5; done
}

if [ "${1:-}" = "--retirer" ]; then
  arreter
  rm -f "$PLIST"
  echo "Lancement automatique retiré. Code dans $ICI et données dans ~/.dashboard-claude conservés."
  exit 0
fi

# 0. Vérification préalable : rien n'est installé si un indispensable manque
./verifier.sh --silencieux || { echo "Installation arrêtée : corrige d'abord ce qui est marqué ✘ (détail : ./verifier.sh)."; exit 1; }

# Ancien nom du service (premières versions) : arrêté et remplacé
if [ -n "$ANCIENNE" ] && [ -f "$HOME/Library/LaunchAgents/$ANCIENNE.plist" ]; then
  launchctl bootout "$DOMAINE/$ANCIENNE" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$ANCIENNE.plist"
fi

# 1. Copie du code : version enregistrée dans git si c'est un dépôt, sinon le dossier tel quel
mkdir -p "$ICI"
rm -rf "$ICI/app.nouveau"
mkdir "$ICI/app.nouveau"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git archive HEAD | tar -x -C "$ICI/app.nouveau"
else
  rsync -a --exclude .git --exclude .venv --exclude __pycache__ --exclude .claude ./ "$ICI/app.nouveau/"
fi
rm -rf "$ICI/app.ancien"
[ -d "$ICI/app" ] && mv "$ICI/app" "$ICI/app.ancien"
mv "$ICI/app.nouveau" "$ICI/app"

# 2. Python isolé
if [ ! -x "$ICI/venv/bin/python" ]; then
  PY=$(./verifier.sh --python) || exit 1
  "$PY" -m venv "$ICI/venv"
fi
"$ICI/venv/bin/pip" install -q -r "$ICI/app/requirements.txt"

# 3. Démarrage automatique (relancé s'il s'arrête)
# Le service ne lit pas ton profil de terminal : on lui donne le dossier où se trouve « claude »
DOSSIER_CLAUDE=$(dirname "$(PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH" command -v claude)")
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.dashboard-claude"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$ETIQUETTE</string>
  <key>ProgramArguments</key><array><string>$ICI/venv/bin/python</string><string>-m</string><string>app.serveur</string></array>
  <key>WorkingDirectory</key><string>$ICI/app</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$DOSSIER_CLAUDE:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key><string>$HOME</string>
    <key>DASHBOARD_PORT</key><string>$PORT</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$HOME/.dashboard-claude/serveur.log</string>
  <key>StandardErrorPath</key><string>$HOME/.dashboard-claude/serveur.log</string>
</dict></plist>
EOF
plutil -lint "$PLIST" >/dev/null

# Libère le port si un serveur lancé à la main tourne encore
if lsof -ti "tcp:$PORT" >/dev/null 2>&1 && ! launchctl print "$DOMAINE/$ETIQUETTE" >/dev/null 2>&1; then
  kill $(lsof -ti "tcp:$PORT") 2>/dev/null || true
  sleep 1
fi
arreter
launchctl bootstrap "$DOMAINE" "$PLIST"

# 4. Raccourci pour le Dock
mkdir -p "$HOME/Applications"
osacompile -o "$HOME/Applications/Mon Claude.app" -e "open location \"http://127.0.0.1:$PORT/\"" >/dev/null
# Icône maison (source : installation/icone-mac.svg) à la place de celle d'AppleScript
APPLI="$HOME/Applications/Mon Claude.app"
cp "$ICI/app/installation/icone.icns" "$APPLI/Contents/Resources/applet.icns"
rm -f "$APPLI/Contents/Resources/Assets.car"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$APPLI/Contents/Info.plist" 2>/dev/null || true
codesign --force --sign - "$APPLI" >/dev/null 2>&1 || true   # le paquet a changé : on le re-signe localement
touch "$APPLI"

for _ in $(seq 1 40); do curl -s -m 1 "http://127.0.0.1:$PORT/api/sante" >/dev/null && break; sleep 0.5; done
if curl -s -m 2 "http://127.0.0.1:$PORT/api/sante" >/dev/null; then
  echo "Mon Claude est installé et lancé : http://127.0.0.1:$PORT/"
  echo "Raccourci : ~/Applications/Mon Claude.app (glisse-le dans le Dock)."
else
  echo "Installé, mais le serveur ne répond pas. Journal : ~/.dashboard-claude/serveur.log"
  exit 1
fi
