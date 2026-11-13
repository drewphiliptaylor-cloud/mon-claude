# Installer Mon Claude — guide pas à pas

Mon Claude est une interface graphique locale pour **Claude Code** : un accueil en widgets,
des conversations en direct, une action rapide, une to-do, ton agenda.
Tout tourne **sur ton Mac**. Rien n'est hébergé ailleurs.

Compte **15 minutes** pour une première installation (sans la dictée).

---

## Ce qu'il te faut

| Quoi | Pourquoi | Obligatoire ? |
|---|---|---|
| Un **Mac** (macOS récent) | le démarrage automatique utilise les outils de macOS | oui |
| Un **abonnement Claude Pro ou Max** | Mon Claude utilise ton abonnement, pas une clé API payante | oui |
| **Claude Code** installé et connecté | c'est lui qui fait le travail ; Mon Claude n'en est que l'interface | oui |
| **Python 3.10 ou plus** (3.12 conseillé) | fait tourner le petit serveur local | oui |
| **Homebrew** | installe Python et la dictée en une commande | conseillé |
| **whisper-cpp** + modèle vocal (~550 Mo) | la dictée au micro, transcrite sur ton Mac | non |
| **Google Chrome** | ouvrir Mon Claude dans sa propre fenêtre, sans onglets | non |

Pas de panique : le script `verifier.sh` regarde tout ça pour toi et te dit quoi faire.

---

## Étape 1 — Ouvrir le Terminal dans le dossier de Mon Claude

1. Copie le dossier `mon-claude` où tu veux (par exemple dans ton dossier personnel).
2. Ouvre l'appli **Terminal** (`Cmd + Espace`, tape « Terminal », `Entrée`).
3. Tape `cd ` (avec un espace), **glisse le dossier** `mon-claude` dans la fenêtre du Terminal, puis `Entrée`.

## Étape 2 — Vérifier ta configuration

```bash
./verifier.sh
```

Tu obtiens un bilan :

- **✔** : prêt.
- **✘** : indispensable et manquant. Une flèche **→** te dit exactement quoi faire.
- **⚠** : optionnel. Une fonction sera simplement indisponible (la dictée, par exemple).

Corrige chaque **✘**, puis relance `./verifier.sh`, jusqu'à lire :
« Tout l'indispensable est prêt ».

### Les corrections les plus courantes

**Homebrew absent** — colle la commande donnée sur https://brew.sh, puis suis ce qu'elle affiche à la fin
(deux lignes à copier pour que le Terminal trouve `brew`).

**Python introuvable** :
```bash
brew install python@3.12
```

**Claude Code introuvable** — suis la page officielle :
https://docs.claude.com/fr/docs/claude-code/setup

**Claude Code pas connecté** :
```bash
claude
```
Puis suis les étapes de connexion avec ton compte Claude (abonnement Pro ou Max).
Quand Claude Code te répond, tape `/exit` pour quitter.

**« Connecté, mais pas par un abonnement »** — Claude Code utilise une clé API : chaque message serait facturé.
Lance `claude`, tape `/login` et choisis ton compte claude.ai.

## Étape 3 — Installer

```bash
./installer.sh
```

Le script :
1. refait la vérification (il s'arrête si un **✘** reste) ;
2. copie le code dans `~/.local/share/mon-claude` (ton dossier de départ n'est jamais modifié) ;
3. crée un environnement Python isolé, sans toucher au reste de ton Mac ;
4. inscrit Mon Claude au **démarrage automatique** (il se relance tout seul s'il s'arrête) ;
5. crée l'appli **`~/Applications/Mon Claude.app`**.

À la fin, tu lis : « Mon Claude est installé et lancé : http://127.0.0.1:8765/ ».

## Étape 4 — Premier lancement

1. Ouvre le Finder → `Cmd + Maj + H` (ton dossier personnel) → **Applications** → double-clic sur **Mon Claude**.
2. Glisse **Mon Claude** dans le **Dock** pour l'avoir sous la main.
3. Dans Mon Claude, ouvre **Réglages** (en bas du menu de gauche) :
   - **Ton prénom** : pour la salutation de l'accueil.
   - **Notifications** : coche « Me prévenir », autorise le navigateur, puis clique sur « Essayer ».
   - **Agenda (lecture)** : colle l'adresse secrète iCal de ton Google Agenda
     (Google Agenda → ⚙ Paramètres → ton agenda → « Adresse secrète au format iCal »).
     Cette adresse reste sur ton Mac.

### Fenêtre dédiée (facultatif, avec Chrome)

Dans Chrome, sur la page Mon Claude : menu **⋮** → « Caster, enregistrer et partager » →
**« Installer la page en tant qu'application »**. Mon Claude s'ouvre alors dans sa propre fenêtre,
avec sa propre icône.

---

## Options

### La dictée au micro

```bash
brew install whisper-cpp
mkdir -p ~/.dashboard-claude/modeles
curl -L -o ~/.dashboard-claude/modeles/ggml-large-v3-turbo-q5_0.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin
```

La voix est transcrite **sur ton Mac**, sans Internet. Le texte arrive dans la zone de saisie ;
il n'est jamais envoyé sans ton clic.

### Le widget « Projets »

Mon Claude lit un tableau dans ton fichier `~/.claude/CLAUDE.md`, sous un titre qui contient le mot
« projets ». Trois colonnes : nom, emplacement, état. Exemple :

```markdown
## Mes projets actifs
| Projet | Emplacement | État |
|---|---|---|
| Site_Atelier | `~/site-atelier/` | en cours — reste : page contact |
```

Sans ce tableau, le widget reste vide : rien ne casse.

### Les tâches

La page « À faire » écrit dans `~/todo/taches.md`, un fichier texte que tu peux aussi modifier à la main.

---

## Ce qu'il faut savoir

- **Sécurité** : le serveur n'écoute que **ton Mac** (adresse 127.0.0.1). Il refuse les requêtes venues d'autres sites.
- **Claude a les mêmes droits que dans le Terminal**, avec tes réglages Claude Code.
  Chaque action sensible affiche une carte **Autoriser / Refuser**.
- **Le quota** affiché vient de la commande `/usage` de Claude Code : elle ne consomme rien.
- **Fermer la page arrête la conversation en cours.** Elle reste dans l'Historique et se reprend plus tard.
- **Tes données** : réglages et images dans `~/.dashboard-claude` ; conversations dans `~/.claude/projects`
  (celles de Claude Code).

## Mettre à jour

Remplace le dossier `mon-claude` par la nouvelle version, puis :
```bash
./installer.sh
```
Tes réglages, ton agenda et tes conversations sont conservés.

## Désinstaller

```bash
./installer.sh --retirer
```
Ça arrête le démarrage automatique. Pour tout effacer ensuite, supprime à la main :
`~/.local/share/mon-claude`, `~/Applications/Mon Claude.app` et, si tu veux aussi perdre tes réglages,
`~/.dashboard-claude`.

## En cas de souci

| Ce que tu vois | Que faire |
|---|---|
| La page ne s'ouvre pas | `./verifier.sh`, puis regarde le journal : `~/.dashboard-claude/serveur.log` |
| « Claude Code n'est pas connecté » dans une conversation | Terminal → `claude` → `/login` |
| Aucune notification | Réglages Système → Notifications → ton navigateur → Autoriser |
| Le micro ne marche pas | `./verifier.sh` (partie Optionnel), puis autorise le micro pour ton navigateur |
| Le port 8765 est pris | `DASHBOARD_PORT=8780 ./installer.sh` |
