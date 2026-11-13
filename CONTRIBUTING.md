# Contribuer à Mon Claude

Merci de ton intérêt ! Toutes les contributions sont bienvenues, même petites.

## Suggérer une idée ou signaler un problème
Ouvre une **issue** (onglet « Issues » du dépôt) :
- **Un problème** : ce que tu faisais, ce que tu attendais, ce qui s'est passé.
  Joins le résultat de `./verifier.sh` et, si possible, la fin de `~/.dashboard-claude/serveur.log`.
  Relis-les d'abord : retire tout ce qui est personnel (noms, chemins, liens d'agenda).
- **Une idée** : le besoin d'abord (« je voudrais pouvoir… »), la solution ensuite si tu en as une.

## Créer ta propre version
Tu peux copier le dépôt (« Fork ») et le modifier comme tu veux : la licence MIT le permet.
Garde simplement le fichier `LICENSE`.

## Proposer une modification
1. Fais un fork, puis une branche pour ta modification.
2. Lance les tests : `.venv/bin/python -m pytest` (crée `.venv` avec `./lancer.sh` la première fois).
3. Ouvre une **pull request** qui explique le pourquoi, et comment tu as vérifié.

## Principes du projet
- **Tout reste sur le Mac de l'utilisateur** : pas de serveur distant, pas de suivi.
- **Rien d'écrit sans validation** : agenda, fichiers, actions de Claude passent par un clic.
- **État visible = état réel** : une fonction pas terminée est affichée grisée, jamais simulée.
- **Accessible** : utilisable au clavier, contrastes suffisants, animations coupées si le Mac le demande.
- **Simple à installer** pour quelqu'un qui débute : `verifier.sh` doit dire quoi faire à chaque manque.
