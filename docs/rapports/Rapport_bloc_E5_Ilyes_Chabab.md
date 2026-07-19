# Monitorage applicatif et résolution d'un incident technique

**Livrable Bloc E5 · Compétences C20 · C21**
Traitement de l'erreur « database is locked » constatée sous écritures concurrentes sur Waterflow 2

**Projet :** Waterflow 2 · **Auteur :** Ilyes Chabab · **Année :** 2025 – 2026 · **Incident :** #001 — 2026-06-15

---

## 1. Contexte

Waterflow 2 stocke ses données (comptes, prélèvements, journal d'audit) dans une base SQLite locale (`data/db/WaterFlowDB.py`), un choix justifié dans le rapport du bloc E4 (C15 §3.3) au regard de la volumétrie visée. Ce même rapport posait une réserve explicite : « remplacer SQLite par une base concurrente-safe (PostgreSQL) si le nombre d'utilisateurs simultanés dépasse le cas d'usage actuel — SQLite verrouille l'écriture au niveau fichier ». Ce cas pratique documente le monitorage qui a permis de détecter cette limite lorsqu'elle s'est concrétisée, puis la résolution de l'incident correspondant.

**Scénario déclencheur (fictif, représentatif d'un cas réel de ce type de projet)** : lors d'une campagne de prélèvement groupée, plusieurs Clients ont soumis des mesures depuis le même créneau horaire via `POST /api/measurements`. Une partie de ces requêtes a échoué avec une erreur serveur 500, chaque requête déclenchant en base à la fois une écriture dans la table `prediction` et une écriture dans la table `audit_logs` via le middleware d'audit déjà présenté dans le rapport du bloc E3 (C9 §2.4).

---

## C20 — Monitorer l'application

### 2.1 Objectif de la compétence

Il s'agissait de surveiller l'application à partir de métriques et de seuils d'alerte définis, avec des outils de collecte, de journalisation et de restitution opérationnels, dans le respect des normes de gestion des données personnelles, afin de permettre la détection automatique de ce type d'incident.

### 2.2 Métrique et seuil ajoutés pour ce risque

La chaîne Prometheus + Alertmanager + Grafana mise en place et testée en bac à sable pour le bloc E3 (C11) est réutilisée sans modification d'infrastructure. Une métrique dédiée à ce risque précis y a été ajoutée.

| Métrique / règle | Seuil d'alerte | Justification |
|---|---|---|
| `db_locked_errors_total` (nouveau compteur, labellisé par `endpoint`) | > 0 sur une fenêtre de 5 minutes | Une erreur de verrou base de données est toujours anormale : aucune tolérance, seuil strict |
| `HighErrorRate` (règle existante, cf bloc E3 C11 §4.4) | Taux de 5xx > 5 % sur 5 min | Règle générique déjà en place, qui s'est effectivement déclenchée lors de l'incident et a corroboré le diagnostic |

```yaml
- alert: DatabaseLocked
  expr: increase(db_locked_errors_total[5m]) > 0
  for: 0m
  labels: {severity: critical}
  annotations:
    summary: "Écriture SQLite en conflit sur {{ $labels.endpoint }}"
```

### 2.3 Journalisation et restitution

Le middleware d'accès existant (`access_log`, `api/main.py`) a été complété d'un niveau `ERROR` explicite au moment de la capture de l'exception SQLite, journalisant l'endpoint, la méthode HTTP, l'identifiant utilisateur et l'horodatage — **jamais les valeurs de mesure elles-mêmes**, par minimisation des données conservées dans les journaux techniques. Un panneau Grafana dédié « Écritures base de données » restitue en temps réel le taux d'erreurs de verrou par endpoint ; ni les journaux ni l'alerte n'exposent de mesure physico-chimique ni de donnée personnelle.

```python
except sqlite3.OperationalError as e:
    logger.error("db_write_conflict", extra={"endpoint": request.url.path,
        "method": request.method, "user_id": current_user.id, "error": str(e)})
    db_locked_errors_total.labels(endpoint=request.url.path).inc()
    raise HTTPException(status_code=503, detail="Service temporairement indisponible, réessayez.")
```

### 2.4 Bilan des critères d'évaluation — C20

| Critère | Statut |
|---|---|
| Métriques et seuils d'alerte définis pour le risque identifié | Acquis |
| Outils adaptés au contexte et aux contraintes techniques (chaîne existante réutilisée) | Acquis |
| Règles de journalisation intégrées, sans donnée personnelle ni mesure brute | Acquis |
| Alerte configurée et en état de marche | Acquis |
| Vecteur de restitution en temps réel disponible (panneau Grafana dédié) | Acquis |

---

## C21 — Résoudre l'incident technique

### 3.1 Objectif de la compétence

Il s'agissait d'identifier la cause de l'incident détecté, de la reproduire, de documenter la procédure de résolution suivie, puis de mettre en œuvre et de versionner une solution garantissant le fonctionnement opérationnel de l'application.

### 3.2 Fiche d'incident

La fiche ci-dessous suit le gabarit standard du projet (`docs/incidents/TEMPLATE.md`), publiée sous `docs/incidents/001-database-is-locked.md`.

**Date :** 2026-06-15, 09h42 → 10h05 (23 min) · **Sévérité :** Majeure · **Auteur :** Ilyes Chabab

**Détection**
L'alerte Prometheus `DatabaseLocked` s'est déclenchée à 09h44, confirmée par un pic visible sur le panneau Grafana « Écritures base de données ». La règle générique `HighErrorRate` (bloc E3) s'est déclenchée trente secondes plus tard, corroborant un taux anormal de réponses 5xx concentré sur `POST /api/measurements`. Le déclenchement fait suite à un signalement de deux Clients sur le terrain observant une erreur au moment de soumettre leur prélèvement pendant une même campagne groupée.

**Diagnostic**
L'incident a été reproduit en environnement de développement à l'aide d'un script envoyant vingt requêtes `POST /api/measurements` concurrentes vers l'API locale :

```python
import concurrent.futures, requests

def submit():
    return requests.post(URL, json=SAMPLE_PAYLOAD, headers=HEADERS)

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(lambda _: submit(), range(20)))

print([r.status_code for r in results])  # plusieurs 500 reproduits
```

Les journaux applicatifs font apparaître de façon reproductible `sqlite3.OperationalError: database is locked`. Analyse de la cause racine :

- chaque requête instancie une connexion SQLite dédiée (`WaterFlowDB()`), sans mode *Write-Ahead Logging* ni délai d'attente explicite configuré à l'ouverture ;
- une même requête écrit deux fois en base de façon séquentielle (table `prediction` puis table `audit_logs` via le middleware d'audit), ce qui allonge la fenêtre pendant laquelle un verrou d'écriture exclusif est détenu ;
- en mode journal par défaut de SQLite (*rollback journal*), une seule connexion peut écrire à la fois ; toute connexion concurrente qui tente d'écrire pendant ce verrou échoue immédiatement au lieu d'attendre, faute de `busy_timeout` configuré.

**Correction**
Quatre changements ont été apportés à `data/db/WaterFlowDB.py`, versionnés sur la branche `fix/sqlite-wal-mode` (Pull Request #6) :

1. activation du mode *Write-Ahead Logging* à l'ouverture de chaque connexion, qui autorise les lectures concurrentes pendant une écriture et réduit fortement la contention ;
2. configuration d'un délai d'attente explicite avant échec, pour que SQLite fasse patienter puis réessaie une écriture en conflit plutôt que d'échouer instantanément ;
3. ajout d'une politique de nouvelle tentative côté application sur les opérations d'écriture critiques, bornée à trois essais, pour absorber une contention résiduelle au-delà du délai d'attente ;
4. ajout d'un test de non-régression rejouant le scénario de charge concurrente du diagnostic.

```python
self.conn = sqlite3.connect(db_name, timeout=5.0)
self.conn.execute("PRAGMA journal_mode=WAL;")
self.conn.execute("PRAGMA busy_timeout=5000;")

# tests/test_pipeline.py
def test_concurrent_writes_no_lock_error(client):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(pool.map(lambda _: client.post(
            "/api/measurements", json=SAMPLE_PAYLOAD, headers=AUTH_HEADERS
        ), range(20)))
    assert all(r.status_code == 200 for r in responses)
```

Après correctif, le même scénario de charge (vingt requêtes concurrentes) ne produit plus aucune erreur 500 ; le test de non-régression ci-dessus a été intégré à la suite `tests/test_pipeline.py` et s'exécute désormais à chaque passage de la chaîne d'intégration continue (bloc E3, C13/C18).

**Prévention**
L'alerte `DatabaseLocked` (§2.2) est conservée en permanence, au-delà de la période de l'incident, afin de détecter toute récidive. La réserve déjà formulée dans la conclusion de la preuve de concept du bloc E4 (C15 §3.5) reste d'actualité : le correctif WAL repousse significativement le seuil de charge concurrente supportable par SQLite, mais ne supprime pas la limite structurelle d'un fichier unique en écriture. Ce point est reporté comme axe de vigilance pour une éventuelle migration vers PostgreSQL si le nombre d'utilisateurs simultanés continuait de croître.

### 3.3 Bilan des critères d'évaluation — C21

| Critère | Statut |
|---|---|
| Cause du problème identifiée correctement | Acquis |
| Problème reproduit en environnement de développement | Acquis |
| Procédure de débogage documentée depuis l'outil de suivi (fiche d'incident) | Acquis |
| Solution documentée explicitant chaque étape de la résolution | Acquis |
| Solution versionnée dans le dépôt Git (Pull Request dédiée) | Acquis |

---

## 4. Conclusion

Le monitorage mis en place pour ce cas pratique a permis de détecter en quelques minutes un incident de contention d'écriture SQLite anticipé dès le bloc E4 mais non encore observé en conditions réelles. Le diagnostic, mené par reproduction systématique plutôt que par supposition, a conduit à un correctif ciblé (mode WAL, délai d'attente, nouvelle tentative applicative) accompagné d'un test de non-régression versionné, tout en documentant honnêtement la limite structurelle qui subsiste au-delà d'un certain volume de charge concurrente.

---
*Ilyes Chabab — Waterflow 2 — 2025-2026*
