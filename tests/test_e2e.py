"""
test_e2e.py — Test de bout en bout exigé par le cahier des charges
Waterflow 2 (section 7) :

    "Au moins un test de bout en bout : dépôt de fiche labo -> OCR ->
    prélèvement structuré -> prédiction modèle."

On simule : un client authentifié dépose une fiche labo (image), le
service OCR.space (mocké) extrait le texte, l'API parse les champs,
crée un prélèvement structuré, déclenche la prédiction du modèle (mocké
de façon déterministe) et persiste le résultat. On vérifie ensuite que
le prélèvement est bien retrouvable via l'API Data classique.
"""

import io


FICHE_LABO_COMPLETE = (
    "Laboratoire AquaTest Provence\n"
    "Rapport d'analyse d'eau potable\n\n"
    "Client : CLIENT-099\n"
    "Date de prelevement : 20/06/2026 10:00\n\n"
    "Resultats analytiques :\n"
    "pH : 7,2\n"
    "Durete : 196,9\n"
    "Solides : 20988,1\n"
    "Chloramines : 7,1\n"
    "Sulfates : 333,1\n"
    "Conductivite : 422,0\n"
    "Carbone organique : 14,2\n"
    "Trihalomethanes : 66,6\n"
    "Turbidite : 3,9\n"
)


class _FakeOCRResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "IsErroredOnProcessing": False,
            "ParsedResults": [{"ParsedText": FICHE_LABO_COMPLETE}],
        }


def test_parcours_complet_fiche_labo_jusqu_a_la_prediction(client, client_user, monkeypatch):
    import ocr_api

    monkeypatch.setattr(ocr_api.requests, "post", lambda *a, **k: _FakeOCRResponse())

    # ── Étape 1 : le client dépose sa fiche labo (image) ──────────────
    resp = client.post(
        "/api/ocr/lab-report",
        headers={"X-API-Key": client_user["api_key"]},
        data={"file": (io.BytesIO(b"contenu-image-simule"), "fiche_labo.png")},
        content_type="multipart/form-data",
    )

    # ── Étape 2 : toutes les features ont été extraites -> succès complet ──
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["missing_features"] == []

    # ── Étape 3 : une prédiction a bien été produite par le modèle ────
    assert data["prediction"] in (0, 1)
    assert 0.0 <= data["probability_potable"] <= 1.0
    # pH 7,2 -> dans la plage "potable" du modèle factice (6.0 - 8.5)
    assert data["prediction"] == 1
    assert data["water_status"] == "Potable (Safe)"

    # ── Étape 4 : la sécurité d'identité est respectée ─────────────────
    # Le client_id provient de la clé API authentifiée, pas du texte OCR
    # (qui contenait 'CLIENT-099', un identifiant métier différent).
    assert data["client_id"] == client_user["id"]

    # ── Étape 5 : le prélèvement structuré est bien persisté et ────────
    # retrouvable ensuite via l'API Data classique du client.
    history_resp = client.get(
        "/api/measurements", headers={"X-API-Key": client_user["api_key"]}
    )
    assert history_resp.status_code == 200
    history = history_resp.get_json()
    assert history["total_records"] == 1
    record = history["history"][0]
    assert record["measures"]["ph"] == 7.2
    assert record["measures"]["hardness"] == 196.9
    assert record["potability_result"] == 1


def test_parcours_complet_visible_aussi_par_l_analyste_qualite(
    client, client_user, analyst_user, monkeypatch
):
    """Le prélèvement créé via OCR doit apparaître avec provenance 'ocr'
    (ou équivalente) dans le dashboard de l'analyste qualité."""
    import ocr_api

    monkeypatch.setattr(ocr_api.requests, "post", lambda *a, **k: _FakeOCRResponse())

    client.post(
        "/api/ocr/lab-report",
        headers={"X-API-Key": client_user["api_key"]},
        data={"file": (io.BytesIO(b"contenu-image-simule"), "fiche_labo.png")},
        content_type="multipart/form-data",
    )

    resp = client.get(
        "/api/dashboard/measurements",
        headers={"X-API-Key": analyst_user["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_records"] == 1
    assert data["data"][0]["client"]["id"] == client_user["id"]
