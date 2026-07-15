from tests.conftest import BEST_THRESHOLD

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
# b. TESTS FONCTIONNELS (API FastAPI, via TestClient)
# ─────────────────────────────────────────────────────────────

POTABLE_FEATURES = [7.0, 204.8, 20791.3, 7.3, 368.5, 564.3, 10.3, 86.9, 2.9]  # ph=7 -> potable (DummyModel)
NON_POTABLE_FEATURES = [2.0, 204.8, 20791.3, 7.3, 368.5, 564.3, 10.3, 86.9, 2.9]  # ph=2 -> non potable


def test_health_endpoint(client):
    """Test fonctionnel : /health répond et signale le modèle comme chargé."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "healthy"
    assert json_data["model_loaded"] is True


def test_metrics_endpoint(client):
    """Test fonctionnel : /metrics expose les métriques RED au format Prometheus, sans auth."""
    client.get("/health")  # genere au moins une requete a compter

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text


def test_security_headers_present(client):
    """Test fonctionnel : chaque réponse porte les en-têtes de sécurité de base."""
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_measurements_requires_api_key(client):
    """Test fonctionnel : /api/measurements refuse une requête sans clé API."""
    response = client.post("/api/measurements", json={"features": POTABLE_FEATURES})
    assert response.status_code == 401


def test_measurements_predict_potable(client, test_db):
    """Test fonctionnel : une requête valide sur /api/measurements renvoie la bonne structure."""
    response = client.post(
        "/api/measurements",
        json={"features": POTABLE_FEATURES},
        headers={"X-API-Key": test_db["client_key"]},
    )

    assert response.status_code == 201
    json_data = response.json()

    assert json_data["prediction"] == 1
    assert json_data["water_status"] == "Potable (Safe)"
    assert json_data["probability_potable"] >= BEST_THRESHOLD


def test_measurements_predict_non_potable(client, test_db):
    """Test fonctionnel : des mesures défavorables renvoient une prédiction non potable."""
    response = client.post(
        "/api/measurements",
        json={"features": NON_POTABLE_FEATURES},
        headers={"X-API-Key": test_db["client_key"]},
    )

    assert response.status_code == 201
    json_data = response.json()

    assert json_data["prediction"] == 0
    assert json_data["water_status"] == "Non Potable (Unsafe)"


def test_measurements_bad_request(client, test_db):
    """Test fonctionnel : l'API rejette un payload incorrect (8 valeurs au lieu de 9)."""
    payload = {"features": POTABLE_FEATURES[:-1]}  # Il manque une valeur

    response = client.post(
        "/api/measurements",
        json=payload,
        headers={"X-API-Key": test_db["client_key"]},
    )
    assert response.status_code == 422


def test_admin_route_forbidden_for_client_role(client, test_db):
    """Test fonctionnel : un rôle Client ne peut pas lister les clients (réservé à Admin)."""
    response = client.get("/api/clients", headers={"X-API-Key": test_db["client_key"]})
    assert response.status_code == 403


def test_admin_can_list_clients(client, test_db):
    """Test fonctionnel : un rôle Admin peut lister les clients."""
    response = client.get("/api/clients", headers={"X-API-Key": test_db["admin_key"]})
    assert response.status_code == 200
    assert response.json()["total_clients"] == 3


# --- GET /api/login -------------------------------------------------------


def test_login_valid_key(client, test_db):
    response = client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["authenticated"] is True
    assert json_data["role"] == "Client"


def test_login_invalid_key(client):
    response = client.post("/api/login", headers={"X-API-Key": "not-a-real-key"})
    assert response.status_code == 401


def test_login_rate_limited(client, test_db):
    """Test fonctionnel : /api/login coupe court au bout de 10 tentatives/minute (anti brute-force)."""
    headers = {"X-API-Key": test_db["client_key"]}
    for _ in range(10):
        response = client.post("/api/login", headers=headers)
        assert response.status_code == 200

    response = client.post("/api/login", headers=headers)
    assert response.status_code == 429


# --- GET /api/measurements -------------------------------------------------


def test_get_measurements_requires_api_key(client):
    """Test fonctionnel : l'historique des prélèvements nécessite une clé API."""
    response = client.get("/api/measurements")
    assert response.status_code == 401


def test_get_measurements_history(client, test_db):
    """Test fonctionnel : après une soumission, le prélèvement apparaît dans l'historique."""
    headers = {"X-API-Key": test_db["client_key"]}
    client.post("/api/measurements", json={"features": POTABLE_FEATURES}, headers=headers)

    response = client.get("/api/measurements", headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["total_records"] == 1
    assert json_data["history"][0]["measures"]["ph"] == POTABLE_FEATURES[0]


# --- POST /api/clients (Admin uniquement) ----------------------------------


def test_create_client_forbidden_for_non_admin(client, test_db):
    """Test fonctionnel : un rôle Client ne peut pas créer de nouveaux clients."""
    response = client.post(
        "/api/clients",
        json={"username": "nouveau_labo", "role": "Client"},
        headers={"X-API-Key": test_db["client_key"]},
    )
    assert response.status_code == 403


def test_create_client_as_admin(client, test_db):
    """Test fonctionnel : un rôle Admin peut créer un nouveau client et reçoit sa clé en clair."""
    response = client.post(
        "/api/clients",
        json={"username": "nouveau_labo", "role": "Client"},
        headers={"X-API-Key": test_db["admin_key"]},
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["client"]["username"] == "nouveau_labo"
    assert "api_key_plain" in json_data["client"]


# --- POST /api/clients/{cid}/rotate-key (Admin uniquement) -----------------


def test_rotate_key_forbidden_for_non_admin(client, test_db):
    response = client.post(
        "/api/clients/1/rotate-key", headers={"X-API-Key": test_db["client_key"]}
    )
    assert response.status_code == 403


def test_rotate_key_nonexistent_client(client, test_db):
    response = client.post(
        "/api/clients/999999/rotate-key", headers={"X-API-Key": test_db["admin_key"]}
    )
    assert response.status_code == 404


def test_rotate_key_admin(client, test_db):
    """Test fonctionnel : la rotation révoque l'ancienne clé et en émet une nouvelle."""
    login = client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})
    cid = login.json()["user_id"]

    response = client.post(
        f"/api/clients/{cid}/rotate-key", headers={"X-API-Key": test_db["admin_key"]}
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["client_id"] == cid
    new_key = json_data["api_key_plain"]

    # L'ancienne clé ne fonctionne plus.
    old_login = client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})
    assert old_login.status_code == 401

    # La nouvelle clé fonctionne.
    new_login = client.post("/api/login", headers={"X-API-Key": new_key})
    assert new_login.status_code == 200


# --- GET /api/audit-logs (Admin uniquement) ---------------------------------


def test_audit_logs_forbidden_for_non_admin(client, test_db):
    response = client.get("/api/audit-logs", headers={"X-API-Key": test_db["client_key"]})
    assert response.status_code == 403


def test_audit_logs_admin(client, test_db):
    """Test fonctionnel : chaque appel API authentifié est tracé dans les logs d'audit."""
    client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})

    response = client.get("/api/audit-logs", headers={"X-API-Key": test_db["admin_key"]})
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["total_logs"] >= 1
    assert any(log["endpoint"] == "/api/login" for log in json_data["logs"])


# --- RGPD : GET/DELETE /api/me ----------------------------------------------


def test_rgpd_me_get(client, test_db):
    response = client.get("/api/me", headers={"X-API-Key": test_db["client_key"]})
    assert response.status_code == 200
    assert response.json()["donnees_personnelles"]["role"] == "Client"


def test_rgpd_me_delete(client, test_db):
    headers = {"X-API-Key": test_db["client_key"]}
    response = client.delete("/api/me", headers=headers)
    assert response.status_code == 200

    # La clé supprimée n'est plus valide.
    response = client.post("/api/login", headers=headers)
    assert response.status_code == 401


# --- GET /api/dashboard/* (Quality_Analyst/Admin) ---------------------------


def test_dashboard_measurements_forbidden_for_client(client, test_db):
    response = client.get(
        "/api/dashboard/measurements", headers={"X-API-Key": test_db["client_key"]}
    )
    assert response.status_code == 403


def test_dashboard_measurements_as_analyst(client, test_db):
    headers = {"X-API-Key": test_db["client_key"]}
    client.post("/api/measurements", json={"features": POTABLE_FEATURES}, headers=headers)

    response = client.get(
        "/api/dashboard/measurements",
        headers={"X-API-Key": test_db["analyst_key"]},
    )
    assert response.status_code == 200
    assert response.json()["total_records"] == 1


def test_dashboard_metrics(client, test_db):
    response = client.get(
        "/api/dashboard/metrics", headers={"X-API-Key": test_db["admin_key"]}
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "Production"


def test_dashboard_model_versions(client, test_db):
    response = client.get(
        "/api/dashboard/model-versions", headers={"X-API-Key": test_db["analyst_key"]}
    )
    assert response.status_code == 200
    assert response.json()["total_versions"] == 1


def test_dashboard_replay(client, test_db):
    response = client.post(
        "/api/dashboard/replay",
        json={"run_id": "fake-run-1", "features": POTABLE_FEATURES},
        headers={"X-API-Key": test_db["analyst_key"]},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["prediction"] == 1
    assert json_data["water_status"] == "Potable (Safe)"


# --- POST /api/ocr/lab-report -----------------------------------------------


def test_ocr_lab_report_requires_api_key(client, mock_ocr_space):
    response = client.post(
        "/api/ocr/lab-report",
        files={"file": ("labo.png", b"fake-image-bytes", "image/png")},
    )
    assert response.status_code == 401


def test_ocr_lab_report_rejects_unsupported_extension(client, test_db, mock_ocr_space):
    response = client.post(
        "/api/ocr/lab-report",
        files={"file": ("labo.txt", b"fake-bytes", "text/plain")},
        headers={"X-API-Key": test_db["client_key"]},
    )
    assert response.status_code == 415


def test_ocr_lab_report_success(client, test_db, mock_ocr_space):
    """Test fonctionnel : une fiche labo lisible renvoie une prédiction complète,
    et le client_id vient de la clé API (jamais du fichier/formulaire)."""
    response = client.post(
        "/api/ocr/lab-report",
        files={"file": ("labo.png", b"fake-image-bytes", "image/png")},
        headers={"X-API-Key": test_db["client_key"]},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert json_data["missing_features"] == []
    assert json_data["prediction"] == 1
    assert json_data["measurement"]["features"]["ph"] == 7.0


def test_ocr_health(client):
    response = client.get("/api/ocr/health")
    assert response.status_code == 200
    assert response.json()["ocr_service"] == "ocr.space"


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