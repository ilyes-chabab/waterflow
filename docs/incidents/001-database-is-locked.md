# Incident #001 — Écritures SQLite en conflit sous charge concurrente

**Date** : 2026-06-15, 09h42 → 10h05 (23 min)
**Sévérité** : Majeure
**Auteur** : Ilyes Chabab

## Contexte

Waterflow 2 stocke ses données (comptes, prélèvements, journal d'audit) dans une base SQLite
locale (`data/db/WaterFlowDB.py`), un choix justifié dans le rapport du bloc E4 au regard de la
volumétrie visée. Ce même rapport posait une réserve explicite : *« remplacer SQLite par une base
concurrente-safe (PostgreSQL) si le nombre d'utilisateurs simultanés dépasse le cas d'usage
actuel — SQLite verrouille l'écriture au niveau fichier »*. Cet incident documente le moment où
cette limite s'est concrétisée.

**Scénario déclencheur** (fictif, représentatif d'un cas réel de ce type de projet) : lors d'une
campagne de prélèvement groupée, plusieurs Clients ont soumis des mesures depuis le même créneau
horaire via `POST /api/measurements`. Une partie de ces requêtes a échoué avec une erreur serveur
500 — chaque requête déclenchant en base à la fois une écriture dans `prediction` et une écriture
dans `audit_logs` via le middleware d'audit (`api/main.py::access_log`).

## Détection

L'alerte Prometheus `DatabaseLocked` (`alert_rules.yml`) se déclenche dès la première occurrence
de `db_locked_errors_total` sur une fenêtre de 5 minutes (`for: 0m`) — aucune tolérance, une erreur
de verrou est toujours anormale. La règle générique `HighErrorRate` (bloc E3) se serait également
déclenchée en parallèle, corroborant un taux anormal de réponses 5xx concentré sur
`POST /api/measurements`.

## Diagnostic

**Cause racine identifiée**, en trois points :

1. Chaque requête instanciait une connexion SQLite dédiée (`WaterFlowDB()`), sans mode
   Write-Ahead Logging ni délai d'attente explicite configuré à l'ouverture
   (`sqlite3.connect(db_name)` nu).
2. Une même requête écrit deux fois en base de façon séquentielle (`prediction` puis
   `audit_logs` via le middleware d'audit), ce qui allonge la fenêtre pendant laquelle un verrou
   d'écriture exclusif est détenu.
3. En mode journal par défaut de SQLite (rollback journal), une seule connexion peut écrire à la
   fois ; toute connexion concurrente qui tente d'écrire pendant ce verrou échoue immédiatement
   au lieu d'attendre, faute de `busy_timeout` configuré.

**Limite honnête sur la reproduction** : une tentative de reproduction automatisée (20-60 écritures
concurrentes via des threads Python, avec et sans le correctif) n'a **pas** permis de déclencher
l'erreur de façon fiable dans cet environnement de développement — les écritures SQLite sont assez
rapides, et le GIL Python sérialise suffisamment l'exécution, pour que deux écritures se
chevauchent rarement à cette échelle sur une machine de développement. La cause racine ci-dessus
reste valide (documentée dans la littérature SQLite et confirmée par la structure du code), mais
je ne prétends pas avoir un test qui échoue de façon démontrée sans le correctif — c'est une
limite assumée de ce cas pratique plutôt qu'une preuve dissimulée. Le test de non-régression
(`tests/test_pipeline.py::test_concurrent_writes_no_lock_error`) reste utile comme garde-fou
fonctionnel (l'application répond correctement sous charge), pas comme preuve rouge/vert de la
régression exacte.

## Correction

Quatre changements apportés à `data/db/WaterFlowDB.py` :

1. **Mode Write-Ahead Logging (WAL)** activé à l'ouverture de chaque connexion
   (`PRAGMA journal_mode=WAL;`) — autorise les lectures concurrentes pendant une écriture et
   réduit fortement la contention.
2. **Délai d'attente explicite** avant échec (`timeout=5.0` sur `sqlite3.connect`,
   `PRAGMA busy_timeout=5000;`) — une connexion qui trouve la base verrouillée patiente jusqu'à
   5s avant d'échouer, plutôt que d'échouer instantanément.
3. **Nouvelle tentative applicative** bornée à 3 essais (`_commit_with_retry`) sur les écritures
   critiques (`add_prediction`, `add_audit_log`) — absorbe une contention résiduelle qui
   subsisterait malgré WAL + busy_timeout sous forte concurrence.
4. **Interception explicite** de `sqlite3.OperationalError` dans la route
   `POST /api/measurements` (`api/main.py`) : journalisation minimisée (endpoint, méthode,
   utilisateur, horodatage — jamais les valeurs de mesure), incrément de
   `db_locked_errors_total{endpoint=...}`, réponse `503` explicite plutôt qu'un `500` non géré.

Versionné sur la branche `fix/sqlite-wal-mode`.

## Prévention

L'alerte `DatabaseLocked` est conservée en permanence, au-delà de la période de l'incident, pour
détecter toute récidive. Réserve déjà formulée dès le bloc E4 : le correctif WAL repousse
significativement le seuil de charge concurrente supportable par SQLite, mais ne supprime pas la
limite structurelle d'un fichier unique en écriture — axe de vigilance pour une éventuelle
migration vers PostgreSQL si le nombre d'utilisateurs simultanés continuait de croître.
