"""
conftest.py — Fixtures partagées pour la suite de tests Waterflow 2.

Stratégie de mocking :
- MLflow n'est pas disponible / pas de serveur MLflow en environnement de
  test : on injecte un faux module `mlflow` dans sys.modules AVANT
  l'import de `app.py`, afin que le chargement du modèle au démarrage de
  l'app ne plante pas et reste déterministe.
- La base de données réelle (WaterFlowDB) est remplacée par une base
  SQLite temporaire et isolée à chaque test, pour ne jamais toucher la
  vraie base de données et garantir l'indépendance des tests.
- Le service OCR.space est mocké (jamais d'appel réseau réel en test).
"""

import sys
import types
import hashlib
import secrets
import tempfile
import os
import pytest


# ──────────────────────────────────────────────────────────
# 1. Mock de MLflow avant tout import de app.py / ocr_api.py
# ──────────────────────────────────────────────────────────

class _FakeModel:
    """Modèle ML factice : renvoie une probabilité déterministe.

    On simule un comportement réaliste : si le ph (1ere feature) est
    proche de 7 et les autres valeurs 'raisonnables', on renvoie une
    eau potable, sinon non potable. Mais pour la plupart des tests, on
    veut juste un résultat déterministe et contrôlable, donc on se base
    sur la somme des features pour produire une probabilité stable.
    """

    def predict_proba(self, features_array):
        import numpy as np
        row = features_array[0]
        # Heuristique simple et déterministe pour les tests
        ph = row[0]
        prob_potable = 0.9 if 6.0 <= ph <= 8.5 else 0.1
        return np.array([[1 - prob_potable, prob_potable]])


def _install_fake_mlflow():
    """Injecte un module mlflow factice dans sys.modules."""
    fake_mlflow = types.ModuleType("mlflow")
    fake_mlflow_xgboost = types.ModuleType("mlflow.xgboost")
    fake_mlflow_tracking = types.ModuleType("mlflow.tracking")

    fake_mlflow.set_tracking_uri = lambda uri: None

    def _load_model(uri):
        return _FakeModel()

    fake_mlflow_xgboost.load_model = _load_model

    class _FakeVersion:
        def __init__(self, version="1", run_id="fakerun123", stage="Production"):
            self.version = version
            self.run_id = run_id
            self.current_stage = stage

    class _FakeRun:
        def __init__(self):
            self.data = types.SimpleNamespace(
                metrics={"accuracy": 0.91, "f1_score": 0.88,
                         "precision": 0.87, "recall": 0.89},
                params={"n_estimators": "300", "max_depth": "5"},
            )

    class _FakeMlflowClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_latest_versions(self, name, stages=None):
            return [_FakeVersion()]

        def get_run(self, run_id):
            return _FakeRun()

        def search_model_versions(self, filter_string):
            return [_FakeVersion(version="1"), _FakeVersion(version="2")]

        def get_experiment_by_name(self, name):
            return None

        def create_experiment(self, name):
            return "0"

        def transition_model_version_stage(self, **kwargs):
            return None

    fake_mlflow_tracking.MlflowClient = _FakeMlflowClient

    fake_mlflow.xgboost = fake_mlflow_xgboost
    fake_mlflow.tracking = fake_mlflow_tracking

    sys.modules["mlflow"] = fake_mlflow
    sys.modules["mlflow.xgboost"] = fake_mlflow_xgboost
    sys.modules["mlflow.tracking"] = fake_mlflow_tracking

    return fake_mlflow, fake_mlflow_xgboost, fake_mlflow_tracking


_install_fake_mlflow()


# ──────────────────────────────────────────────────────────
# 2. Base de données de test (isolée, SQLite temporaire)
# ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_db_path(tmp_path):
    """Chemin vers une base SQLite temporaire et vide pour chaque test."""
    return str(tmp_path / "test_waterflow.db")


@pytest.fixture(autouse=True)
def patch_waterflow_db(monkeypatch, temp_db_path):
    """
    Force toute instanciation de WaterFlowDB (dans app.py et ocr_api.py)
    à utiliser la base de test temporaire plutôt que la base réelle.
    """
    import data.db.WaterFlowDB as wf_module

    original_init = wf_module.WaterFlowDB.__init__

    def patched_init(self, db_name=temp_db_path):
        original_init(self, db_name=db_name)

    monkeypatch.setattr(wf_module.WaterFlowDB, "__init__", patched_init)
    yield


# ──────────────────────────────────────────────────────────
# 3. Application Flask (app.py) chargée après les mocks
# ──────────────────────────────────────────────────────────

@pytest.fixture
def app(patch_waterflow_db):
    """Importe app.py (après mock MLflow) et fournit l'app Flask."""
    # Import différé : doit arriver après l'installation des mocks et
    # après le patch de la DB, car app.py charge le modèle et crée les
    # tables dès l'import.
    import importlib
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    return app_module


@pytest.fixture
def client(app):
    """Client de test Flask."""
    return app.app.test_client()


# ──────────────────────────────────────────────────────────
# 4. Helpers : création d'utilisateurs / clés API de test
# ──────────────────────────────────────────────────────────

def _make_api_key():
    return secrets.token_hex(32)


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


@pytest.fixture
def create_user(app):
    """Factory pour créer un utilisateur en base et récupérer sa clé API en clair."""
    from data.db.WaterFlowDB import WaterFlowDB

    created = []

    def _create(username="test_client", role="Client"):
        plain_key = _make_api_key()
        hashed = _hash(plain_key)
        db = WaterFlowDB()
        db.add_user(username=username, api_key=hashed, right=role)
        users = db.get_users()
        db.close()
        user = next(u for u in users if u[2] == hashed)
        created.append(user)
        return {"id": user[0], "username": username, "role": role, "api_key": plain_key}

    return _create


@pytest.fixture
def client_user(create_user):
    """Un client final déjà créé en base, prêt à l'emploi."""
    return create_user(username="client_042", role="Client")


@pytest.fixture
def admin_user(create_user):
    """Un administrateur déjà créé en base, prêt à l'emploi."""
    return create_user(username="admin_test", role="Admin")


@pytest.fixture
def analyst_user(create_user):
    """Un analyste qualité déjà créé en base, prêt à l'emploi."""
    return create_user(username="analyst_test", role="Quality_Analyst")


VALID_FEATURES = [7.0, 196.9, 20000.0, 7.1, 333.0, 420.0, 14.2, 66.6, 3.9]
