"""
test_ocr_api.py — Tests de l'API OCR : validation des fichiers, parsing
des fiches labo, et gestion des erreurs/incidents liés à OCR.space.

OCR.space n'est jamais appelé réellement : `requests.post` est mocké
dans chaque test pour simuler les réponses du service externe.
"""

import io
import requests
import pytest


SAMPLE_LAB_REPORT_TEXT = (
    "Laboratoire AquaTest Provence\n"
    "Rapport d'analyse d'eau potable\n\n"
    "Client : CLIENT-042 - M. Martin\n"
    "Adresse : 12 rue des Sources, 13009 Marseille\n"
    "Type de prelevement : Puits prive\n"
    "Date de prelevement : 18/03/2025 09:30\n\n"
    "Resultats analytiques :\n"
    "pH : 7,6\n"
    "Conductivite : 650 uS/cm\n"
    "Temperature : 16,2 C\n"
    "Turbidite : 0,7 NTU\n"
    "Durete : 25,3 f\n"
    "Nitrates (NO3-) : 32,5 mg/L\n"
    "Nitrites (NO2-) : 0,03 mg/L\n"
    "Ammonium (NH4+) : 0,04 mg/L\n"
    "Chlorures (Cl-) : 140 mg/L\n"
    "Sulfates (SO4--) : 210 mg/L\n"
    "Fer total : 0,08 mg/L\n"
    "Manganese : 0,01 mg/L\n"
)


def _fake_ocr_success_response(text=SAMPLE_LAB_REPORT_TEXT):
    """Construit une réponse JSON factice imitant OCR.space."""
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "IsErroredOnProcessing": False,
                "ParsedResults": [{"ParsedText": text}],
            }

    return _Resp()


def _fake_ocr_error_response(message="Fichier illisible"):
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"IsErroredOnProcessing": True, "ErrorMessage": [message]}

    return _Resp()


def _make_file(content=b"fake-image-bytes", filename="rapport.png"):
    return (io.BytesIO(content), filename)


class TestFileValidation:

    def test_pas_de_fichier_renvoie_400(self, client, client_user):
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_nom_de_fichier_vide_renvoie_400(self, client, client_user):
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": (io.BytesIO(b"data"), "")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_extension_non_supportee_renvoie_415(self, client, client_user):
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file(filename="rapport.exe")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 415

    def test_fichier_trop_volumineux_renvoie_413(self, client, client_user, monkeypatch):
        import ocr_api
        monkeypatch.setattr(ocr_api, "MAX_FILE_SIZE_MB", 0.000001)  # ~1 octet
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file(content=b"contenu un peu plus long que 1 octet")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 413

    def test_sans_cle_api_renvoie_401(self, client):
        resp = client.post(
            "/api/ocr/lab-report",
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 401


class TestOCRIntegrationSuccess:

    def test_fiche_complete_renvoie_prediction(self, client, client_user, monkeypatch):
        """Fiche labo avec toutes les mesures -> prélèvement structuré + prédiction."""
        import ocr_api
        monkeypatch.setattr(
            ocr_api.requests, "post",
            lambda *a, **k: _fake_ocr_success_response()
        )

        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )

        data = resp.get_json()
        assert resp.status_code in (200, 202)
        assert data["measurement_payload"]["features"]["ph"] == 7.6
        # Fiche AquaTest type ne contient pas tous les champs du modèle
        # (ex. solids/TDS absent) -> partial_match attendu
        assert "missing_features" in data

    def test_fiche_incomplete_renvoie_202_partial_match(self, client, client_user, monkeypatch):
        import ocr_api
        incomplete_text = "Client : CLIENT-001\npH : 7,2\n"
        monkeypatch.setattr(
            ocr_api.requests, "post",
            lambda *a, **k: _fake_ocr_success_response(text=incomplete_text)
        )

        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["status"] == "partial_match"
        assert len(data["missing_features"]) > 0
        assert data["prediction"] is None

    def test_client_id_authentifie_prevaut_sur_celui_extrait_ocr(self, client, client_user, monkeypatch):
        """Sécurité : l'ID client vient de la clé API, jamais du texte OCR."""
        import ocr_api
        monkeypatch.setattr(
            ocr_api.requests, "post",
            lambda *a, **k: _fake_ocr_success_response()
        )
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["client_id"] == client_user["id"]
        assert data["measurement_payload"]["client_id"] == client_user["id"]


class TestOCRIncidents:
    """Scénarios d'incident attendus par le cahier des charges
    (service OCR indisponible, fichier illisible, etc.)."""

    def test_ocr_timeout_renvoie_504(self, client, client_user, monkeypatch):
        import ocr_api

        def _raise_timeout(*a, **k):
            raise requests.exceptions.Timeout()

        monkeypatch.setattr(ocr_api.requests, "post", _raise_timeout)
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 504
        assert resp.get_json()["incident"] == "OCR_TIMEOUT"

    def test_ocr_service_indisponible_renvoie_502(self, client, client_user, monkeypatch):
        import ocr_api

        def _raise_connection_error(*a, **k):
            raise requests.exceptions.ConnectionError()

        monkeypatch.setattr(ocr_api.requests, "post", _raise_connection_error)
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 502
        assert resp.get_json()["incident"] == "OCR_UNREACHABLE"

    def test_fichier_illisible_renvoie_422(self, client, client_user, monkeypatch):
        import ocr_api
        monkeypatch.setattr(
            ocr_api.requests, "post",
            lambda *a, **k: _fake_ocr_error_response("Fichier illisible")
        )
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 422
        assert resp.get_json()["incident"] == "OCR_PROCESSING_ERROR"

    def test_resultat_ocr_vide_renvoie_422(self, client, client_user, monkeypatch):
        import ocr_api
        monkeypatch.setattr(
            ocr_api.requests, "post",
            lambda *a, **k: _fake_ocr_success_response(text="   ")
        )
        resp = client.post(
            "/api/ocr/lab-report",
            headers={"X-API-Key": client_user["api_key"]},
            data={"file": _make_file()},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 422
        assert resp.get_json()["incident"] == "OCR_EMPTY_RESULT"


def test_ocr_health_endpoint(client):
    resp = client.get("/api/ocr/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ocr_service"] == "ocr.space"
    assert "api_key_configured" in data
