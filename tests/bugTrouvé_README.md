# Bugs trouvés et interprétation des résultats de tests — Waterflow 2

Ce document trace deux incidents réels rencontrés sur la chaîne CI (`.github/workflows/ci.yml`),
diagnostiqués et corrigés sur la branche `fix-ci-pytest`. Objectif : montrer que les résultats de
tests (pass/fail, codes de sortie, logs) ont été lus et interprétés, pas seulement constatés.

---

## Incident 1 — `ModuleNotFoundError: No module named 'data'`

**Constat** : en local, `python -m pytest` donnait 32/32 tests passés. Sur GitHub Actions, la
même suite échouait avant même l'exécution d'un seul test, avec un code de sortie **4** (erreur
d'usage/config pytest — à distinguer d'un code **1**, qui signale des tests qui échouent
réellement).

**Log observé** :
```
ImportError while loading conftest '/home/runner/work/waterflow2/waterflow2/tests/conftest.py'.
tests/conftest.py:18: in <module>
    from data.db.WaterFlowDB import WaterFlowDB
E   ModuleNotFoundError: No module named 'data'
Error: Process completed with exit code 4.
```

**Diagnostic** : `ci.yml` lançait `pytest` (sans `python -m`). Contrairement à `python -m pytest`,
qui ajoute automatiquement le répertoire courant à `sys.path`, un simple `pytest` s'appuie sur son
propre mécanisme d'insertion de chemin. Comme `tests/` ne contient pas de `__init__.py`, pytest
insère `tests/` lui-même dans `sys.path` plutôt que la racine du projet — le package `data/`, qui
vit à la racine, devient donc introuvable. En local le bug était invisible car `python -m pytest`
masque ce problème.

**Correction** : `.github/workflows/ci.yml` — remplacement de `run: pytest` par
`run: python -m pytest` (commit `36a3b6b`, "fix ci yml"), pour aligner l'invocation CI sur celle
utilisée en local.

---

## Incident 2 — `test_health_endpoint` échoue avec `model_loaded: False`

**Constat** : une fois l'incident 1 corrigé, la CI passait à 31 tests réussis / 1 échoué. Le seul
test en échec, `test_health_endpoint`, est le premier test de la suite à utiliser la fixture
`client` (donc le premier à déclencher le chargement du modèle MLflow).

**Log observé** :
```
assert json_data["model_loaded"] is True
E       assert False is True
---------------------------- Captured stdout setup -----------------------------
Erreur chargement modèle : API request to http://127.0.0.1:5000/api/2.0/mlflow/registered-models/get-latest-versions failed
with exception HTTPConnectionPool(host='127.0.0.1', port=5000): Max retries exceeded ...
```

**Diagnostic** : le test tentait réellement de contacter un serveur MLflow sur `127.0.0.1:5000`,
alors que la fixture `client` (`tests/conftest.py`) est censée remplacer
`mlflow.xgboost.load_model` par un `DummyModel` factice, sans réseau. Le mock
(`monkeypatch.setattr("mlflow.xgboost.load_model", ...)`) n'était donc pas actif au moment précis
du démarrage de l'application (`lifespan` dans `api/main.py`), uniquement pour ce tout premier
appel de la session de tests.

Élément de contexte : le log CI montre `pytest-9.1.1`, contre `pytest-7.4.3` en local — comme
`requirements.txt` ne fixe aucune version, la CI installe systématiquement les dernières versions
disponibles (dont `mlflow`), ce qui peut faire diverger le comportement d'un environnement à
l'autre. Piste retenue : les versions récentes de MLflow chargent certains modules "flavor"
(`mlflow.xgboost`) en lazy-loading, remplaçant potentiellement le module patché par sa version
réelle au premier accès effectif — écrasant le mock juste avant qu'il ne serve.

**Correction** : plutôt que de tenter de figer une version exacte de `mlflow` (fragile et à
reproduire à chaque mise à jour), la fixture `client` force désormais explicitement le modèle
factice sur l'application une fois le `TestClient` démarré, indépendamment de ce qui s'est passé
pendant le `lifespan` :

```python
with TestClient(app) as c:
    c.app.state.model = DummyModel()
    yield c
```

(`tests/conftest.py`, commit `cfd73c3`, "fix test model mock"). Cette approche est robuste aux
évolutions internes de MLflow, puisqu'elle ne dépend plus de l'endroit exact où le modèle est
chargé en interne.

---

## Résultat final

Run CI complet et vert sur `fix-ci-pytest` (id `28558610639`) : `Validate raw data` → `Run tests`
(32/32) → `Train & validate model (F1-score gate)`, les trois étapes réussissent sans erreur.
