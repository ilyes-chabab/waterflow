"""
test_model_api.py — Tests de l'API Model : pipeline de prédiction,
métriques MLflow et rejeu de prédiction sur une version donnée.

Le serveur MLflow réel n'est jamais sollicité : voir conftest.py pour le
mock complet de mlflow / mlflow.xgboost / mlflow.tracking.
"""

from conftest import VALID_FEATURES


class TestPredictionPipeline:

    def test_prediction_eau_potable_ph_neutre(self, client, client_user):
        """Avec un pH neutre (~7), le modèle factice prédit 'potable'."""
        features = [7.0, 196.9, 20000.0, 7.1, 333.0, 420.0, 14.2, 66.6, 3.9]
        resp = client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"features": features},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["prediction"] == 1
        assert data["water_status"] == "Potable (Safe)"
        assert 0.0 <= data["probability_potable"] <= 1.0

    def test_prediction_eau_non_potable_ph_extreme(self, client, client_user):
        """Avec un pH extrême (hors 6-8.5), le modèle factice prédit 'non potable'."""
        features = [1.0, 196.9, 20000.0, 7.1, 333.0, 420.0, 14.2, 66.6, 3.9]
        resp = client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"features": features},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["prediction"] == 0
        assert data["water_status"] == "Non Potable (Unsafe)"

    def test_prediction_persistee_en_base(self, client, client_user):
        """La prédiction doit être historisée et retrouvable via GET /api/measurements."""
        client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"features": VALID_FEATURES},
        )
        resp = client.get("/api/measurements", headers={"X-API-Key": client_user["api_key"]})
        data = resp.get_json()
        assert data["total_records"] == 1
        record = data["history"][0]
        assert record["measures"]["ph"] == VALID_FEATURES[0]
        assert record["potability_result"] in (0, 1)


class TestModelMetricsDashboard:

    def test_metriques_modele_production_accessibles_analyste(self, client, analyst_user):
        resp = client.get(
            "/api/dashboard/metrics",
            headers={"X-API-Key": analyst_user["api_key"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "metrics" in data
        assert "accuracy" in data["metrics"]
        assert data["version"] == "1"

    def test_metriques_modele_refusees_a_un_client(self, client, client_user):
        resp = client.get(
            "/api/dashboard/metrics",
            headers={"X-API-Key": client_user["api_key"]},
        )
        assert resp.status_code == 403

    def test_liste_versions_modele(self, client, analyst_user):
        resp = client.get(
            "/api/dashboard/model-versions",
            headers={"X-API-Key": analyst_user["api_key"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_versions"] == 2
        assert all("run_id" in v for v in data["versions"])


class TestReplayPrediction:

    def test_rejeu_prediction_avec_run_id_valide(self, client, analyst_user):
        resp = client.post(
            "/api/dashboard/replay",
            headers={"X-API-Key": analyst_user["api_key"]},
            json={"run_id": "fakerun123", "features": VALID_FEATURES},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["run_id"] == "fakerun123"
        assert "probability_potable" in data

    def test_rejeu_prediction_format_invalide(self, client, analyst_user):
        resp = client.post(
            "/api/dashboard/replay",
            headers={"X-API-Key": analyst_user["api_key"]},
            json={"run_id": "fakerun123"},  # 'features' manquant
        )
        assert resp.status_code == 400

    def test_rejeu_prediction_refuse_a_un_client(self, client, client_user):
        resp = client.post(
            "/api/dashboard/replay",
            headers={"X-API-Key": client_user["api_key"]},
            json={"run_id": "fakerun123", "features": VALID_FEATURES},
        )
        assert resp.status_code == 403

    def test_rejeu_prediction_nombre_features_incorrect(self, client, analyst_user):
        resp = client.post(
            "/api/dashboard/replay",
            headers={"X-API-Key": analyst_user["api_key"]},
            json={"run_id": "fakerun123", "features": [1, 2, 3]},
        )
        assert resp.status_code == 400
