"""
test_ui_integration.py - Tests d'intégration UI <-> API (Waterflow 2).

Utilise streamlit.testing.v1.AppTest pour exécuter réellement les pages Streamlit
(views/*.py, dashboard_qualite.py) et le fixture `ui_client` (tests/conftest.py) qui
redirige requests.get/post/delete vers le vrai TestClient FastAPI : ces tests exercent
donc les vraies routes API (auth, DB de test, modèle factice), pas des réponses mockées
à la main. Complète tests/test_pipeline.py, qui ne teste que l'API en direct, jamais
la couche Streamlit qui la consomme.
"""

from streamlit.testing.v1 import AppTest

POTABLE_FEATURES = [7.0, 204.8, 20791.3, 7.3, 368.5, 564.3, 10.3, 86.9, 2.9]


def test_ui_panel_test_prediction(ui_client, test_db):
    """views/panel_test.py : le bouton de prédiction appelle réellement POST /api/measurements."""
    at = AppTest.from_file("views/panel_test.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["api_key"] = test_db["client_key"]
    at.session_state["current_features"] = POTABLE_FEATURES
    at.run()

    assert not at.exception

    predict_btn = next(b for b in at.button if b.label == "Lancer la prédiction API")
    predict_btn.click().run()

    assert not at.exception
    assert any("Potable (Safe)" in s.value for s in at.success)


def test_ui_panel_test_requires_all_features(ui_client, test_db):
    """views/panel_test.py : refuse d'appeler l'API si une caractéristique est à 0.0."""
    at = AppTest.from_file("views/panel_test.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    predict_btn = next(b for b in at.button if b.label == "Lancer la prédiction API")
    predict_btn.click().run()

    assert not at.exception
    assert any("Impossible de lancer la prédiction" in e.value for e in at.error)


def test_ui_historique_shows_real_data(ui_client, test_db):
    """views/historique.py : affiche l'historique réellement enregistré via POST /api/measurements."""
    headers = {"X-API-Key": test_db["client_key"]}
    ui_client.post("/api/measurements", json={"features": POTABLE_FEATURES}, headers=headers)

    at = AppTest.from_file("views/historique.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["user_id"] = 2
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    assert not at.exception
    assert len(at.dataframe) == 1


def test_ui_historique_empty_state(ui_client, test_db):
    """views/historique.py : message informatif si aucun prélèvement (pas d'erreur)."""
    at = AppTest.from_file("views/historique.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    assert not at.exception
    assert len(at.dataframe) == 0
    assert any("aucun prélèvement" in i.value.lower() for i in at.info)


def test_ui_accueil_admin_shows_real_data(ui_client, test_db):
    """views/accueil_admin.py : liste réellement les comptes (GET /api/clients) et les logs (GET /api/audit-logs)."""
    at = AppTest.from_file("views/accueil_admin.py")
    at.session_state["api_key"] = test_db["admin_key"]
    at.run()

    assert not at.exception
    # Un tableau pour les comptes, un pour les logs d'audit
    assert len(at.dataframe) == 2


def test_ui_accueil_admin_forbidden_for_client(ui_client, test_db):
    """views/accueil_admin.py : un rôle Client se voit refuser l'accès (403 relayé par l'API)."""
    at = AppTest.from_file("views/accueil_admin.py")
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    assert not at.exception
    assert any("Droits insuffisants" in e.value for e in at.error)


def test_ui_securite_admin_create_client(ui_client, test_db):
    """views/securite_admin.py : le formulaire de création appelle réellement POST /api/clients."""
    at = AppTest.from_file("views/securite_admin.py")
    at.session_state["api_key"] = test_db["admin_key"]
    at.run()

    at.text_input[0].input("nouveau_labo_ui").run()
    at.button[0].click().run()

    assert not at.exception
    assert at.session_state["last_created_client"]["username"] == "nouveau_labo_ui"
    assert "api_key_plain" in at.session_state["last_created_client"]


def test_ui_securite_admin_rotate_key(ui_client, test_db):
    """views/securite_admin.py : le bouton de rotation appelle réellement POST /api/clients/{id}/rotate-key,
    et l'ancienne clé du compte ciblé cesse ensuite de fonctionner (vérifié via l'API)."""
    at = AppTest.from_file("views/securite_admin.py")
    at.session_state["api_key"] = test_db["admin_key"]
    at.run()
    assert not at.exception

    # selectbox[0] = role du formulaire de creation ; selectbox[1] = compte cible de la rotation.
    # Cible le compte client_test (pas la clé admin utilisee par la page elle-meme).
    at.selectbox[1].select("ID 2 - client_test (Client)").run()
    rotate_btn = next(b for b in at.button if b.label == "Régénérer la clé")
    rotate_btn.click().run()

    assert not at.exception
    assert at.session_state["last_rotated_key"]["id"] == 2

    old_login = ui_client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})
    assert old_login.status_code == 401

    new_key = at.session_state["last_rotated_key"]["key"]
    new_login = ui_client.post("/api/login", headers={"X-API-Key": new_key})
    assert new_login.status_code == 200


def test_ui_mes_donnees_shows_real_data(ui_client, test_db):
    """views/mes_donnees.py : affiche réellement les données du compte via GET /api/me."""
    at = AppTest.from_file("views/mes_donnees.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    assert not at.exception
    assert any("client_test" in m.value for m in at.markdown)


def test_ui_mes_donnees_delete_requires_confirmation(ui_client, test_db):
    """views/mes_donnees.py : le bouton de suppression reste désactivé sans coche de confirmation."""
    at = AppTest.from_file("views/mes_donnees.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    assert not at.exception
    delete_btn = next(b for b in at.button if b.label == "Supprimer mon compte")
    assert delete_btn.disabled is True

    # La cle est toujours valide : la suppression n'a jamais ete declenchee.
    login = ui_client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})
    assert login.status_code == 200


def test_ui_mes_donnees_delete_with_confirmation(ui_client, test_db):
    """views/mes_donnees.py : coche + bouton appelle réellement DELETE /api/me."""
    at = AppTest.from_file("views/mes_donnees.py")
    at.session_state["logged_in"] = True
    at.session_state["username"] = "client_test"
    at.session_state["api_key"] = test_db["client_key"]
    at.run()

    at.checkbox[0].check().run()
    delete_btn = next(b for b in at.button if b.label == "Supprimer mon compte")
    assert delete_btn.disabled is False
    delete_btn.click().run()

    assert not at.exception
    assert at.session_state["logged_in"] is False

    login = ui_client.post("/api/login", headers={"X-API-Key": test_db["client_key"]})
    assert login.status_code == 401


def test_ui_dashboard_qualite_shows_real_data(ui_client, test_db):
    """dashboard_qualite.py : les 3 onglets appellent réellement les routes /api/dashboard/*."""
    at = AppTest.from_file("dashboard_qualite.py")
    at.session_state["username"] = "analyst_test"
    at.session_state["role"] = "Quality_Analyst"
    at.session_state["api_key"] = test_db["analyst_key"]
    at.run()

    assert not at.exception
    assert len(at.error) == 0
    # Onglet metriques : les metriques du modele Production (FakeMlflowClient) sont affichees
    assert len(at.metric) >= 1
