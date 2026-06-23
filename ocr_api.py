"""
ocr_api.py – Blueprint Flask pour l'ingestion OCR (Waterflow 2)
Route principale : POST /api/ocr/lab-report
Utilise OCR.space pour extraire les données d'une fiche labo (image ou PDF).
"""

import os
import re
import requests
from flask import Blueprint, jsonify, request

# ──────────────────────────────────────────────
# Blueprint
# ──────────────────────────────────────────────
ocr_bp = Blueprint("ocr", __name__, url_prefix="/api/ocr")

# Clé API OCR.space — à mettre dans vos variables d'environnement
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")
OCR_SPACE_URL = "https://api.ocr.space/parse/image"

# Taille max acceptée (10 Mo)
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "bmp", "tiff"}


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    """Vérifie que l'extension du fichier est autorisée."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def call_ocr_space(file_bytes: bytes, filename: str) -> dict:
    """
    Envoie le fichier à OCR.space et retourne la réponse JSON brute.
    Lève une exception en cas d'erreur réseau ou de refus de l'API.
    """
    is_pdf = filename.lower().endswith(".pdf")

    payload = {
        "apikey": OCR_SPACE_API_KEY,
        "language": "fre",
        "isOverlayRequired": False,
        "OCREngine": 2,
        "scale": True,
        "isTable": True,
    }

    if is_pdf:
        payload["filetype"] = "PDF"

    files = {"file": (filename, file_bytes, "application/octet-stream")}

    response = requests.post(
        OCR_SPACE_URL,
        data=payload,
        files=files,
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()

    # OCR.space signale ses propres erreurs dans le JSON
    if result.get("IsErroredOnProcessing"):
        error_msg = result.get("ErrorMessage", ["Erreur OCR inconnue"])
        raise ValueError(f"OCR.space error: {error_msg}")

    return result


def extract_text_from_ocr_response(ocr_response: dict) -> str:
    """Concatène le texte de toutes les pages retournées par OCR.space."""
    pages = ocr_response.get("ParsedResults", [])
    return "\n".join(page.get("ParsedText", "") for page in pages)


def parse_lab_report(raw_text: str) -> dict:
    """
    Extrait les champs physico-chimiques du texte brut OCR.
    Reprend la logique de votre script OCR local (regex robustes).
    Retourne un dict avec None pour les champs non trouvés.
    """
    data = {
        "client_id":       None,
        "date_prelevement": None,
        "ph":              None,
        "hardness":        None,   # Dureté  → mappé sur Hardness du modèle
        "solids":          None,   # Solides dissous totaux (TDS)
        "chloramines":     None,
        "sulfate":         None,
        "conductivity":    None,   # Conductivité
        "organic_carbon":  None,
        "trihalomethanes": None,
        "turbidity":       None,   # Turbidité
        # Champs bonus présents sur les fiches AquaTest
        "nitrates":        None,
        "nitrites":        None,
        "ammonium":        None,
        "chlorures":       None,
        "fer":             None,
        "manganese":       None,
    }

    # ── Métadonnées ──────────────────────────────────────
    m = re.search(r"Client\s*[:\-]\s*([A-Z0-9\-]+)", raw_text)
    if m:
        data["client_id"] = m.group(1).strip()

    m = re.search(r"Date\s+de\s+pr[eé]l[eè]vement\s*[:\-]\s*([\d/]+(?:\s+[\d:]+)?)", raw_text, re.IGNORECASE)
    if m:
        data["date_prelevement"] = m.group(1).strip()

    # ── Mesures physico-chimiques ─────────────────────────
    # Chaque pattern tente de capturer un nombre décimal (virgule ou point)
    patterns = {
        "ph":               r"pH\s*[:\-]\s*([\d,.]+)",
        "hardness":        r"Dur[eé]t[eé]\s*[:\-]\s*([\d,.]+)",
        "solids":          r"(?:Solides?|TDS|Total\s+Dissolved)\s*[:\-]\s*([\d,.]+)",
        "chloramines":     r"Chloramines?\s*[:\-]\s*([\d,.]+)",
        "sulfate":         r"Sulfates?.*?[:\-]\s*([\d,.]+)",
        "conductivity":    r"Conductivit[eé]\s*[:\-]\s*([\d,.]+)",
        "organic_carbon":  r"(?:Carbone\s+organique|COT|TOC)\s*[:\-]\s*([\d,.]+)",
        "trihalomethanes": r"(?:Trihal[oe]m[eé]thanes?|THM)\s*[:\-]\s*([\d,.]+)",
        "turbidity":       r"Turbidi[tée]+\s*[:\-]\s*([\d,.]+)",
        
        "nitrates":        r"Nitrates?.*?[:\-]\s*([\d,.]+)",
        "nitrites":        r"Nitrites?.*?[:\-]\s*([\d,.]+)",
        "ammonium":        r"Ammonium.*?[:\-]\s*([\d,.]+)",
        "chlorures":       r"Chlorures?.*?[:\-]\s*([\d,.]+)",
        "fer":             r"Fer.*?[:\-]\s*([\d,.]+)",
        "manganese":       r"Mangan[eè]se.*?[:\-]\s*([\d,.]+)",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            try:
                data[key] = float(m.group(1).replace(",", "."))
            except ValueError:
                pass  # on laisse None si conversion impossible

    return data


def build_measurement_payload(parsed: dict, client_id_override: str | None = None) -> dict:
    """
    Construit le payload structuré compatible avec POST /api/measurements.
    Les 9 features du modèle sont extraites ; les champs manquants restent None.
    """
    return {
        "client_id":        client_id_override or parsed.get("client_id"),
        "date_prelevement": parsed.get("date_prelevement"),
        "provenance":       "OCR",
        "features": {
            "ph":              parsed.get("ph"),
            "hardness":        parsed.get("hardness"),
            "solids":          parsed.get("solids"),
            "chloramines":     parsed.get("chloramines"),
            "sulfate":         parsed.get("sulfate"),
            "conductivity":    parsed.get("conductivity"),
            "organic_carbon":  parsed.get("organic_carbon"),
            "trihalomethanes": parsed.get("trihalomethanes"),
            "turbidity":       parsed.get("turbidity"),
        },
        "extra_fields": {
            "nitrates":    parsed.get("nitrates"),
            "nitrites":    parsed.get("nitrites"),
            "ammonium":    parsed.get("ammonium"),
            "chlorures":   parsed.get("chlorures"),
            "fer":         parsed.get("fer"),
            "manganese":   parsed.get("manganese"),
        },
    }


def count_missing_features(features: dict) -> list[str]:
    """Retourne la liste des features du modèle absentes (None)."""
    return [k for k, v in features.items() if v is None]


# ──────────────────────────────────────────────
# Route principale
# ──────────────────────────────────────────────

@ocr_bp.route("/lab-report", methods=["POST"])
def lab_report():
    """
    POST /api/ocr/lab-report
    Reçoit une fiche labo (image ou PDF), appelle OCR.space,
    parse les données et retourne un prélèvement structuré.

    Headers :
        X-API-Key : clé API du client (obligatoire)

    Body (multipart/form-data) :
        file          : fichier image ou PDF (obligatoire)
        client_id     : surcharge l'ID client extrait par OCR (optionnel)
    """

    # ── 1. Authentification par clé API ──────────────────
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return jsonify({"error": "Clé API manquante (header X-API-Key requis)."}), 401

    # TODO : valider api_key contre la base de données clients
    # client = db.get_client_by_api_key(api_key)
    # if not client:
    #     return jsonify({"error": "Clé API invalide ou expirée."}), 403

    # ── 2. Validation du fichier ──────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni (champ 'file' attendu)."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide."}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": f"Extension non supportée. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}"
        }), 415

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return jsonify({"error": f"Fichier trop volumineux (max {MAX_FILE_SIZE_MB} Mo)."}), 413

    # ── 3. Appel OCR.space ────────────────────────────────
    try:
        ocr_response = call_ocr_space(file_bytes, file.filename)
    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Le service OCR n'a pas répondu à temps (timeout 30 s). Réessayez.",
            "incident": "OCR_TIMEOUT",
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Impossible de joindre OCR.space. Vérifiez la connectivité réseau.",
            "incident": "OCR_UNREACHABLE",
        }), 502
    except requests.exceptions.HTTPError as e:
        return jsonify({
            "error": f"OCR.space a retourné une erreur HTTP : {e}",
            "incident": "OCR_HTTP_ERROR",
        }), 502
    except ValueError as e:
        # Erreur signalée par OCR.space dans le JSON (ex: fichier illisible)
        return jsonify({
            "error": str(e),
            "incident": "OCR_PROCESSING_ERROR",
        }), 422

    # ── 4. Extraction et parsing du texte ─────────────────
    raw_text = extract_text_from_ocr_response(ocr_response)

    if not raw_text.strip():
        return jsonify({
            "error": "OCR n'a extrait aucun texte. Le fichier est peut-être illisible ou vide.",
            "incident": "OCR_EMPTY_RESULT",
        }), 422

    parsed = parse_lab_report(raw_text)

    # Surcharge client_id si passé en form-data
    client_id_override = request.form.get("client_id") or None

    # ── 5. Construction du prélèvement structuré ──────────
    measurement = build_measurement_payload(parsed, client_id_override)

    # ── 6. Vérification des features manquantes ───────────
    missing = count_missing_features(measurement["features"])
    warnings = []
    if missing:
        warnings.append(
            f"Champs non extraits par l'OCR ({len(missing)}/9) : {', '.join(missing)}. "
            "Vérifiez la qualité du document ou complétez manuellement."
        )

    # ── 7. Réponse ────────────────────────────────────────
    response_body = {
        "status": "ok" if not missing else "partial",
        "measurement": measurement,
        "ocr_raw_text": raw_text,   # utile pour debug ; retirez en production si données sensibles
        "warnings": warnings,
    }

    # TODO : persister `measurement` en base de données ici
    # measurement_id = db.insert_measurement(measurement)
    # response_body["measurement_id"] = measurement_id

    return jsonify(response_body), 200 if not missing else 206


# ──────────────────────────────────────────────
# Route de santé OCR
# ──────────────────────────────────────────────

@ocr_bp.route("/health", methods=["GET"])
def ocr_health():
    """GET /api/ocr/health — Vérifie que la clé OCR.space est configurée."""
    key_present = OCR_SPACE_API_KEY not in ("", "helloworld")
    return jsonify({
        "ocr_service": "ocr.space",
        "api_key_configured": key_present,
        "warning": None if key_present else "Clé de démo 'helloworld' active — limites : 1 page, 1 Mo, 25 000 req/mois.",
    }), 200
