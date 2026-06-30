# Tests automatisés — Waterflow 2

Suite de tests PyTest couvrant les exigences de la section 7 du cahier des
charges (« Tests, CI/CD, monitoring et incidents ») :

- **API Data** (`tests/test_data_api.py`) : authentification par clé API,
  gestion des clients (création réservée Admin), dépôt/consultation de
  prélèvements, séparation stricte des périmètres (RGPD), endpoint `/api/me`.
- **API Model** (`tests/test_model_api.py`) : pipeline de prédiction,
  persistance des prédictions, métriques MLflow, comparaison de versions,
  rejeu de prédiction.
- **API OCR** (`tests/test_ocr_api.py`) : validation des fichiers
  (extension, taille, fichier manquant), parsing d'une fiche labo,
  champs manquants (`partial_match`), **scénarios d'incident** (timeout
  OCR, service indisponible, fichier illisible, résultat vide).
- **Bout en bout** (`tests/test_e2e.py`) : dépôt d'une fiche labo → OCR →
  prélèvement structuré → prédiction → consultation par le client et par
  l'analyste qualité.

## Installation

```bash
pip install -r tests/requirements-test.txt
```

## Lancer les tests

```bash
pytest
```

(47 tests, aucune dépendance réseau ni serveur MLflow réel nécessaire.)

## Stratégie de mock (important)

- **MLflow** : aucun serveur MLflow réel n'est requis. `tests/conftest.py`
  injecte un faux module `mlflow` (avec `mlflow.xgboost` et
  `mlflow.tracking.MlflowClient`) **avant** l'import de `app.py`, pour que
  le chargement du modèle au démarrage reste rapide et déterministe.
- **Base de données** : chaque test utilise une base SQLite temporaire
  isolée (`tmp_path`), jamais la base de production.
- **OCR.space** : `requests.post` est mocké dans chaque test OCR ; aucun
  appel réseau réel n'est effectué.

## Bug corrigé pendant l'écriture des tests

`ocr_api.py` comparait la clé API **en clair** reçue dans le header
`X-API-Key` au **hash** stocké en base (alors que `app.py` hash
correctement la clé avant comparaison). En pratique, aucun client ne
pouvait s'authentifier sur la route `/api/ocr/lab-report`. Le correctif
(hash de la clé avant comparaison, cohérent avec `app.py`) est inclus
dans `ocr_api.py`. C'est un bon exemple du scénario d'incident
« authentification incohérente entre modules » à documenter dans
`docs/incidents.md`.
