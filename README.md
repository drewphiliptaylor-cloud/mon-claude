# Mon Claude — dashboard local pour Claude Code

Interface graphique locale pour parler à Claude Code sans terminal : accueil en widgets,
conversations en direct, action rapide, to-do, agenda, teintes.


## Installer (recommandé) : démarre tout seul à l'ouverture de session
Guide pas à pas pour une première installation : **`INSTALLATION.md`**.
```bash
./verifier.sh              # bilan de la configuration, et quoi faire pour chaque manque
./installer.sh             # installe ou met à jour depuis la version enregistrée dans git
./installer.sh --retirer   # retire le démarrage automatique (données conservées)
```
Crée `~/.local/share/mon-claude` (copie du code + Python isolé), un LaunchAgent
`local.mon-claude` (relance automatique) et `~/Applications/Mon Claude.app` à glisser dans le Dock.

## Lancer à la main (développement)
```bash
./lancer.sh
```
Ouvre http://127.0.0.1:8765. Le serveur n'écoute que sur ton Mac.
Arrêter : `kill $(lsof -ti tcp:8765)`.

## Quota en pourcentage
Le serveur lance `/usage` de Claude Code (commande locale, ne consomme pas de quota, ~4 s), au plus une fois
toutes les 3 minutes. Secours : `~/.dashboard-claude/quota.json`, écrit par `~/.claude/statusline.py` quand
un terminal Claude Code est ouvert.

## Notifications
Réglages → Notifications → « Me prévenir ». Prévient quand Claude a répondu ou attend ton accord, si tu es
sur une autre fenêtre. La page doit rester ouverte. Rien ne s'affiche ? Réglages Système → Notifications → ton navigateur.

## Icône et fenêtre dédiée
Source : `installation/icone-mac.svg` (Dock, avec marges macOS) et `web/icone.svg` (onglet, appli installée).
`installer.sh` pose `installation/icone.icns` sur `Mon Claude.app`.
Fenêtre sans onglets : dans Chrome, menu ⋮ → « Caster, enregistrer et partager » → « Installer la page en tant qu'application ».

## Où sont les données
| Quoi | Où |
|---|---|
| Réglages, lien iCal (secret), images jointes | `~/.dashboard-claude/` (hors git) |
| Tâches simples | `~/todo/taches.md` (modifiable à la main) |
| Fiches ICE du skill `/to-do` | `~/todo/todo.md` (lecture seule) |
| Conversations | celles de Claude Code (`~/.claude/projects`) |
| Projets | tableau « Mes projets actifs » de `~/.claude/CLAUDE.md` + notes du vault |

Chaque chemin se change par variable d'environnement (`DASHBOARD_DATA`, `DASHBOARD_TACHES`,
`DASHBOARD_TODO_ICE`, `DASHBOARD_VAULT`, `DASHBOARD_CLAUDE_MD`, `DASHBOARD_DOSSIER`, `DASHBOARD_PORT`).

## Tests
```bash
.venv/bin/python -m pytest              # rapides, sans réseau ni Claude
.venv/bin/python -m pytest -m reel      # avec le vrai Claude (consomme du quota)
.venv/bin/python tests/navigateur.py accueil /tmp/captures   # parcours dans Chrome (serveur lancé)
```

## Fonctions (au 13/11)
Accueil en widgets (agenda, à faire, reprendre, projets, quota, date) · action rapide · conversations en direct
(étapes, orbe, images, autorisations, commandes « / ») · dictée locale (whisper) · brouillons gardés ·
mode clair/sombre/auto · teintes · pages Historique, Projets, À faire, Agenda, Boîte à outils, Travaux en cours,
Galerie, Ce que je retiens, Antisèche, Réglages. Encore grisé : Routines.

## Limites connues (v1)
- Dictée : nécessite `whisper-cli` (Homebrew) et le modèle `~/.dashboard-claude/modeles/ggml-large-v3-turbo-q5_0.bin` (chemins réglables : `DASHBOARD_WHISPER`, `DASHBOARD_WHISPER_MODELE`).
- Un skill qui lance lui-même une commande (`!commande` dans son SKILL.md, ex. `/statusline-aide`) est refusé par Claude Code hors terminal : le message d'erreur s'affiche dans la conversation.
- Les réflexions de Claude ne sont pas transmises par Claude Code : le fil montre les actions réelles.
- Le pourcentage de quota est lu dans le texte de `/usage` (en anglais) : si Claude Code change sa formulation, le widget retombe sur l'état seul.
- L'ajout direct dans Google Agenda s'active dans Réglages ; testé « à blanc » (Claude prépare le bon appel), jamais écrit pour de vrai par les tests.
- Réordonner les widgets : glisser à la souris, ou flèches ← → en mode « Modifier ».

## Licence et contributions
Licence **MIT** (`LICENSE`) : tu peux utiliser Mon Claude, le modifier, en faire ta propre version
et la partager, à condition de garder la mention de licence.
Idées, problèmes, améliorations : voir `CONTRIBUTING.md`.

Mon Claude est un projet indépendant : il n'est ni produit ni soutenu par Anthropic.
Il s'appuie sur Claude Code et sur ton propre abonnement Claude.
