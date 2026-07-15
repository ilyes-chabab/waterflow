"""
conftest.py - Fixtures partagées pour les tests de l'API FastAPI Waterflow 2.

Isole complètement les tests de l'environnement réel :
- une base SQLite temporaire remplace data/db/waterflow.db (aucune donnée réelle touchée)
- un faux modèle MLflow remplace le modèle XGBoost chargé au démarrage (pas besoin
  d'un serveur MLflow lancé pour faire tourner la suite de tests)
- un faux MlflowClient remplace les appels au registre de modèles (routes /api/dashboard/*)
- un faux appel HTTP remplace OCR.space (route /api/ocr/lab-report)
"""

import hashlib
import urllib.parse

import numpy as np
import pytest
from fastapi.testclient import TestClient

from data.db.WaterFlowDB import WaterFlowDB

BEST_THRESHOLD = 0.37


class DummyModel:
    """Modèle XGBoost factice : potable si ph (1ère feature) >= 5."""

    def predict_proba(self, arr):
        ph = arr[0][0]
        prob_potable = 0.8 if ph >= 5 else 0.1
        return np.array([[1 - prob_potable, prob_potable]])


class FakeVersion:
    def __init__(self, version, run_id, stage):
        self.version = version
        self.run_id = run_id
        self.current_stage = stage


class FakeRunData:
    def __init__(self, metrics, params):
        self.metrics = metrics
        self.params = params


class FakeRun:
    def __init__(self, metrics, params):
        self.data = FakeRunData(metrics, params)


class FakeMlflowClient:
    """Remplace mlflow.tracking.MlflowClient : renvoie une version 'Production'
    factice sans appeler le vrai serveur MLflow (routes /api/dashboard/*)."""

    _VERSIONS = [FakeVersion("1", "fake-run-1", "Production")]
    _METRICS = {"f1_score": 0.58, "accuracy": 0.75}
    _PARAMS = {"n_estimators": "200"}

    def get_latest_versions(self, name, stages=None):
        return self._VERSIONS

    def search_model_versions(self, filter_string):
        return self._VERSIONS

    def get_run(self, run_id):
        return FakeRun(self._METRICS, self._PARAMS)


OCR_SAMPLE_TEXT = (
    "Client: CL-001\n"
    "Date de prélèvement: 01/07/2026\n"
    "pH: 7.0\n"
    "Dureté: 204.8\n"
    "Solides: 20791.3\n"
    "Chloramines: 7.3\n"
    "Sulfates: 368.5\n"
    "Conductivité: 564.3\n"
    "Carbone organique: 10.3\n"
    "Trihalométhanes: 86.9\n"
    "Turbidité: 2.9\n"
)


class FakeOCRResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Redirige toute instanciation de WaterFlowDB() vers une base SQLite temporaire
    et y crée un Admin, un Client et un Quality_Analyst pour les tests d'authentification."""
    db_path = str(tmp_path / "waterflow_test.db")
    monkeypatch.setattr(WaterFlowDB.__init__, "__defaults__", (db_path,))

    db = WaterFlowDB(db_path)

    admin_key = "admin-test-key"
    client_key = "client-test-key"
    analyst_key = "analyst-test-key"
    db.add_user(
        username="admin_test",
        api_key=hashlib.sha256(admin_key.encode()).hexdigest(),
        right="Admin",
    )
    db.add_user(
        username="client_test",
        api_key=hashlib.sha256(client_key.encode()).hexdigest(),
        right="Client",
    )
    db.add_user(
        username="analyst_test",
        api_key=hashlib.sha256(analyst_key.encode()).hexdigest(),
        right="Quality_Analyst",
    )
    db.close()

    return {
        "db_path": db_path,
        "admin_key": admin_key,
        "client_key": client_key,
        "analyst_key": analyst_key,
    }


@pytest.fixture
def client(test_db, monkeypatch):
    """TestClient FastAPI avec un modèle MLflow et un MlflowClient factices
    (pas de serveur MLflow requis)."""
    monkeypatch.setattr("mlflow.xgboost.load_model", lambda uri: DummyModel())
    monkeypatch.setattr("api.main.MlflowClient", FakeMlflowClient)

    from api.main import app

    app.state.limiter.reset()

    with TestClient(app) as c:
        c.app.state.model = DummyModel()
        yield c


def _url_to_path(url: str) -> str:
    """Retire le scheme+host d'une URL absolue (ex. http://127.0.0.1:8000/api/login)
    pour ne garder que ce que TestClient attend (ex. /api/login)."""
    parsed = urllib.parse.urlparse(url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


@pytest.fixture
def ui_client(client, monkeypatch):
    """Redirige requests.get/post/delete vers le TestClient FastAPI, pour que les
    pages Streamlit (views/*.py, dashboard_qualite.py) soient testées en intégration
    réelle contre l'API (mêmes routes, même DB de test, même modèle factice) sans
    avoir besoin d'un serveur HTTP réellement lancé sur le port 8000."""

    def fake_get(url, headers=None, params=None, **kwargs):
        return client.get(_url_to_path(url), headers=headers, params=params)

    def fake_post(url, headers=None, json=None, data=None, files=None, **kwargs):
        return client.post(_url_to_path(url), headers=headers, json=json, data=data, files=files)

    def fake_delete(url, headers=None, **kwargs):
        return client.delete(_url_to_path(url), headers=headers)

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.delete", fake_delete)

    return client


@pytest.fixture
def mock_ocr_space(monkeypatch):
    """Empêche les tests d'appeler le vrai service OCR.space (réseau)."""

    def fake_post(url, data=None, files=None, timeout=None):
        return FakeOCRResponse({
            "IsErroredOnProcessing": False,
            "ParsedResults": [{"ParsedText": OCR_SAMPLE_TEXT}],
        })

    monkeypatch.setattr("api.ocr_router.requests.post", fake_post)