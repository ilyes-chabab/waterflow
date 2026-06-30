"""
test_data_api.py — Tests de l'API Data : authentification par clé API,
gestion des clients, dépôt et consultation des prélèvements, séparation
des périmètres (RGPD).
"""

import json
from conftest import VALID_FEATURES


# ──────────────────────────────────────────────────────────
# Authentification par clé API
# ──────────────────────────────────────────────────────────

class TestAuthentication:

    def test_login_sans_cle_api_renvoie_401(self, client):
        resp = client.post("/api/login")
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_cle_api_invalide_renvoie_401(self, client):
        resp = client.post("/api/login", headers={"X-API-Key": "cle-invalide"})
        assert resp.status_code == 401

    def test_login_cle_api_valide_renvoie_infos_utilisateur(self, client, client_user):
        resp = client.post("/api/login", headers={"X-API-Key": client_user["api_key"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["authenticated"] is True
        assert data["username"] == client_user["username"]
        assert data["role"] == "Client"

    def test_route_protegee_sans_cle_renvoie_401(self, client):
        resp = client.get("/api/measurements")
        assert resp.status_code == 401

    def test_route_protegee_cle_invalide_renvoie_401(self, client):
        resp = client.get("/api/measurements", headers={"X-API-Key": "fausse-cle"})
        assert resp.status_code == 401

    def test_route_admin_refusee_a_un_client_simple(self, client, client_user):
        resp = client.get("/api/clients", headers={"X-API-Key": client_user["api_key"]})
        assert resp.status_code == 403

    def test_route_admin_autorisee_pour_un_admin(self, client, admin_user):
        resp = client.get("/api/clients", headers={"X-API-Key": admin_user["api_key"]})
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────
# Gestion des clients (création réservée aux administrateurs)
# ──────────────────────────────────────────────────────────

class TestClientManagement:

    def test_creation_client_par_admin(self, client, admin_user):
        resp = client.post(
            "/api/clients",
            headers={"X-API-Key": admin_user["api_key"]},
            json={"username": "nouveau_client", "role": "Client"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["client"]["username"] == "nouveau_client"
        # La clé API en clair doit être renvoyée une seule fois à la création
        assert "api_key_plain" in data["client"]
        assert len(data["client"]["api_key_plain"]) == 64  # token_hex(32)

    def test_creation_client_refusee_pour_un_client_non_admin(self, client, client_user):
        resp = client.post(
            "/api/clients",
            headers={"X-API-Key": client_user["api_key"]},
            json={"username": "intrus"},
        )
        assert resp.status_code == 403

    def test_creation_client_sans_username_renvoie_400(self, client, admin_user):
        resp = client.post(
            "/api/clients",
            headers={"X-API-Key": admin_user["api_key"]},
            json={"role": "Client"},
        )
        assert resp.status_code == 400

    def test_liste_clients_admin_contient_le_hash_pas_la_cle_en_clair(self, client, admin_user, client_user):
        resp = client.get("/api/clients", headers={"X-API-Key": admin_user["api_key"]})
        assert resp.status_code == 200
        data = resp.get_json()
        usernames = [c["username"] for c in data["clients"]]
        assert client_user["username"] in usernames
        # Le hash de la clé doit être présent, jamais la clé en clair
        for c in data["clients"]:
            assert c["api_key_hash"] != client_user.get("api_key")


# ──────────────────────────────────────────────────────────
# Dépôt et consultation de prélèvements (mesures)
# ──────────────────────────────────────────────────────────

class TestMeasurements:

    def test_depot_mesures_valides_renvoie_prediction(self, client, client_user):
        resp = client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"features": VALID_FEATURES},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["client_id"] == client_user["id"]
        assert "prediction" in data
        assert "probability_potable" in data
        assert data["water_status"] in ("Potable (Safe)", "Non Potable (Unsafe)")

    def test_depot_mesures_format_invalide_renvoie_400(self, client, client_user):
        resp = client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"mauvais_champ": "valeur"},
        )
        assert resp.status_code == 400

    def test_depot_mesures_nombre_incorrect_de_features_renvoie_400(self, client, client_user):
        resp = client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"features": [1, 2, 3]},  # seulement 3 valeurs au lieu de 9
        )
        assert resp.status_code == 400
        assert "9 mesures requises" in resp.get_json()["error"]

    def test_consultation_mesures_un_client_ne_voit_que_les_siennes(self, client, create_user):
        """Critère RGPD essentiel : séparation stricte des périmètres."""
        client_a = create_user(username="client_a", role="Client")
        client_b = create_user(username="client_b", role="Client")

        # Le client A dépose un prélèvement
        client.post(
            "/api/measurements",
            headers={"X-API-Key": client_a["api_key"]},
            json={"features": VALID_FEATURES},
        )
        # Le client B dépose un autre prélèvement
        client.post(
            "/api/measurements",
            headers={"X-API-Key": client_b["api_key"]},
            json={"features": VALID_FEATURES},
        )

        resp_a = client.get("/api/measurements", headers={"X-API-Key": client_a["api_key"]})
        resp_b = client.get("/api/measurements", headers={"X-API-Key": client_b["api_key"]})

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        data_a = resp_a.get_json()
        data_b = resp_b.get_json()

        assert data_a["total_records"] == 1
        assert data_b["total_records"] == 1
        assert data_a["client_id"] == client_a["id"]
        assert data_b["client_id"] == client_b["id"]
        # Aucune fuite croisée de données entre clients
        assert data_a["client_id"] != data_b["client_id"]

    def test_consultation_mesures_client_sans_prelevement(self, client, client_user):
        resp = client.get("/api/measurements", headers={"X-API-Key": client_user["api_key"]})
        assert resp.status_code == 200
        assert resp.get_json()["total_records"] == 0


# ──────────────────────────────────────────────────────────
# Dashboard analyste qualité (vue globale filtrable)
# ──────────────────────────────────────────────────────────

class TestDashboardAccess:

    def test_dashboard_mesures_accessible_analyste(self, client, analyst_user, client_user):
        client.post(
            "/api/measurements",
            headers={"X-API-Key": client_user["api_key"]},
            json={"features": VALID_FEATURES},
        )
        resp = client.get(
            "/api/dashboard/measurements",
            headers={"X-API-Key": analyst_user["api_key"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_records"] >= 1

    def test_dashboard_mesures_refuse_a_un_client_simple(self, client, client_user):
        resp = client.get(
            "/api/dashboard/measurements",
            headers={"X-API-Key": client_user["api_key"]},
        )
        assert resp.status_code == 403

    def test_dashboard_filtre_par_client_id(self, client, analyst_user, create_user):
        client_a = create_user(username="filtre_a", role="Client")
        client_b = create_user(username="filtre_b", role="Client")
        client.post("/api/measurements", headers={"X-API-Key": client_a["api_key"]},
                    json={"features": VALID_FEATURES})
        client.post("/api/measurements", headers={"X-API-Key": client_b["api_key"]},
                    json={"features": VALID_FEATURES})

        resp = client.get(
            f"/api/dashboard/measurements?client_id={client_a['id']}",
            headers={"X-API-Key": analyst_user["api_key"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert all(item["client"]["id"] == client_a["id"] for item in data["data"])


# ──────────────────────────────────────────────────────────
# RGPD : droit à l'information
# ──────────────────────────────────────────────────────────

class TestRGPD:

    def test_endpoint_me_renvoie_les_donnees_personnelles(self, client, client_user):
        resp = client.get("/api/me", headers={"X-API-Key": client_user["api_key"]})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["donnees_personnelles"]["id_client"] == client_user["id"]
        assert "regle_conservation" in data

    def test_endpoint_me_necessite_authentification(self, client):
        resp = client.get("/api/me")
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "model_loaded" in data
