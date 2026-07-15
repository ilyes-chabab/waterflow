# Tests - Waterflow 2

Suite de tests pour l'API FastAPI (`api/main.py` + `api/ocr_router.py`).

## Dépendances

Déjà listées dans `requirements.txt` :

- `pytest`
- `pytest-cov` (installe aussi `coverage`)

Installées automatiquement avec FastAPI (nécessaires pour `fastapi.testclient.TestClient`,
absentes en tant que telles de `requirements.txt`) :

- `fastapi`
- `httpx`

```bash
pip install -r requirements.txt
```

## Lancer les tests

```bash
python -m pytest
```

`pytest.ini` restreint la découverte au dossier `tests/` (sinon pytest scanne tout le repo et
essaie d'importer les pages Streamlit de `views/`, qui plantent hors de `streamlit run`).

Lancer un seul fichier ou un seul test :

```bash
python -m pytest tests/test_pipeline.py
python -m pytest tests/test_pipeline.py::test_measurements_predict_potable
```

## Couverture de code

```bash
python -m pytest --cov=api --cov=data.db --cov-report=term-missing
```

Rapport HTML (ouvrir ensuite `htmlcov/index.html`) :

```bash
python -m pytest --cov=api --cov=data.db --cov-report=html
```

## Isolation (`conftest.py`)

Les tests ne touchent jamais l'environnement réel :

- **`test_db`** : redirige toute instanciation de `WaterFlowDB()` vers une base SQLite
  temporaire (`tmp_path`) et y crée un utilisateur `Admin`, `Client` et `Quality_Analyst`.
- **`client`** : `TestClient` FastAPI avec `mlflow.xgboost.load_model` remplacé par un
  `DummyModel` (potable si `ph >= 5`) et `MlflowClient` remplacé par `FakeMlflowClient` —
  aucun serveur MLflow n'est requis.
- **`mock_ocr_space`** : remplace l'appel HTTP à OCR.space par une réponse factice, pour
  tester `/api/ocr/lab-report` sans réseau ni clé API OCR.space réelle.

Ainsi la suite complète tourne en quelques secondes, sans MLflow ni base de données réels.