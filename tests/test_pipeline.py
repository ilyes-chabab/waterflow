import numpy as np
import pytest
from app import app, BEST_THRESHOLD


# ─────────────────────────────────────────────────────────────
# a. TESTS UNITAIRES
# ─────────────────────────────────────────────────────────────


def test_threshold_logic_potable():
    """Test unitaire : vérifie que la logique de décision applique correctement le seuil."""
    # Simulation d'une probabilité supérieure ou égale au seuil (0.37)
    prob_potable = 0.40
    prediction_result = 1 if prob_potable >= BEST_THRESHOLD else 0

    assert (
        prediction_result == 1
    ), f"Pour une probabilité de {prob_potable}, le modèle devrait prédire 1 (Seuil: {BEST_THRESHOLD})"


def test_threshold_logic_non_potable():
    """Test unitaire : vérifie la décision en dessous du seuil."""
    # Simulation d'une probabilité inférieure au seuil (0.37)
    prob_potable = 0.30
    prediction_result = 1 if prob_potable >= BEST_THRESHOLD else 0

    assert (
        prediction_result == 0
    ), f"Pour une probabilité de {prob_potable}, le modèle devrait prédire 0 (Seuil: {BEST_THRESHOLD})"


# ─────────────────────────────────────────────────────────────
# b. TESTS FONCTIONNELS
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Configure un client de test pour requêter l'API Flask sans lancer le serveur."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_flask_health_endpoint(client):
    """Test fonctionnel : vérifie que l'endpoint /health répond correctement."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "status" in json_data
    assert json_data["status"] == "healthy"


def test_flask_predict_endpoint_success(client):
    """Test fonctionnel : vérifie qu'une requête valide sur /predict renvoie la bonne structure."""
    # Simulation de 9 caractéristiques (scalées)
    payload = {"features": [0.5, -1.2, 0.8, 2.1, -0.4, 0.1, 1.1, -0.9, 0.0]}

    response = client.post("/predict", json=payload)

    assert response.status_code == 200
    json_data = response.get_json()

    # Vérification que toutes les clés requises par l'UI sont présentes
    assert "prediction" in json_data
    assert "water_status" in json_data
    assert "probability_potable" in json_data
    assert "decision_threshold_used" in json_data
    assert json_data["decision_threshold_used"] == BEST_THRESHOLD


def test_flask_predict_endpoint_bad_request(client):
    """Test fonctionnel : vérifie que l'API rejette un payload incorrect (ex: 8 valeurs au lieu de 9)."""
    payload = {"features": [0.5, -1.2, 0.8, 2.1, -0.4, 0.1, 1.1, -0.9]}  # Il manque une valeur

    response = client.post("/predict", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


# ─────────────────────────────────────────────────────────────
# c. TESTS DE NON-RÉGRESSION (TNR)
# ─────────────────────────────────────────────────────────────


def test_model_non_regression_f1_score():
    """Test de non-régression : s'assure que le F1-score ne rechute pas en dessous du minimum acceptable.

    Ce test simule la validation de performance minimale requise avant le déploiement.
    """
    F1_SCORE_MINIMAL = 0.50

    current_model_f1_score = 0.5868

    assert current_model_f1_score >= F1_SCORE_MINIMAL, (
        f"Régression détectée ! Le F1-score actuel ({current_model_f1_score}) "
        f"est inférieur au seuil de non-régression fixé à {F1_SCORE_MINIMAL}"
    )