"""
ocr_router.py – Router FastAPI pour l'ingestion OCR (Waterflow 2)
Route principale : POST /api/ocr/lab-report
Utilise OCR.space pour extraire les données d'une fiche labo (image ou PDF).
"""

import os
import re
import numpy as np
import requests
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from prometheus_client import Counter

from data.db.WaterFlowDB import WaterFlowDB
from .auth import get_current_user, UserInfo  # partagé avec main.py
from .logging_config import logger

# ──────────────────────────────────────────────
# Router  (équivalent du Blueprint Flask)
# ──────────────────────────────────────────────
router = APIRouter(prefix="/api/ocr", tags=["OCR"])

OCR_FAILURES = Counter(
    "ocr_failures_total", "Total OCR call failures by reason", ["reason"]
)

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")
OCR_SPACE_URL = "https://api.ocr.space/parse/image"
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "bmp", "tiff"}


# ──────────────────────────────────────────────
# Helpers OCR
# ──────────────────────────────────────────────

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _call_ocr_space(file_bytes: bytes, filename: str) -> dict:
    """Envoie le fichier à OCR.space et retourne la réponse JSON brute."""
    payload = {
        "apikey": OCR_SPACE_API_KEY,
        "language": "fre",
        "isOverlayRequired": False,
        "OCREngine": 2,
        "scale": True,
        "isTable": True,
    }
    if filename.lower().endswith(".pdf"):
        payload["filetype"] = "PDF"

    response = requests.post(
        OCR_SPACE_URL,
        data=payload,
        files={"file": (filename, file_bytes, "application/octet-stream")},
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if result.get("IsErroredOnProcessing"):
        msg = result.get("ErrorMessage", ["Erreur OCR inconnue"])
        raise ValueError(f"OCR.space error: {msg}")

    return result


def _extract_text(ocr_response: dict) -> str:
    pages = ocr_response.get("ParsedResults", [])
    return "\n".join(p.get("ParsedText", "") for p in pages)


def _parse_lab_report(raw_text: str) -> dict:
    """Extrait les champs physico-chimiques du texte brut via regex."""
    data = {k: None for k in [
        "client_id", "date_prelevement",
        "ph", "hardness", "solids", "chloramines", "sulfate",
        "conductivity", "organic_carbon", "trihalomethanes", "turbidity",
        "nitrates", "nitrites", "ammonium", "chlorures", "fer", "manganese",
    ]}

    m = re.search(r"Client\s*[:\-]\s*([A-Z0-9\-]+)", raw_text)
    if m:
        data["client_id"] = m.group(1).strip()

    m = re.search(r"Date\s+de\s+pr[eé]l[eè]vement\s*[:\-]\s*([\d/]+(?:\s+[\d:]+)?)", raw_text, re.IGNORECASE)
    if m:
        data["date_prelevement"] = m.group(1).strip()

    patterns = {
        "ph":              r"pH\s*[:\-]\s*([\d,.]+)",
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
                pass

    return data


MODEL_FEATURE_ORDER = [
    "ph", "hardness", "solids", "chloramines", "sulfate",
    "conductivity", "organic_carbon", "trihalomethanes", "turbidity",
]


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/lab-report", summary="Ingestion OCR d'une fiche labo")
async def lab_report(
    request: Request,
    file: UploadFile = File(..., description="Image ou PDF de la fiche labo"),
    client_id_override: str | None = Form(None, alias="client_id"),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Reçoit une fiche labo (image ou PDF), appelle OCR.space,
    parse les données et retourne un prélèvement structuré + prédiction.

    - **Header requis** : `X-API-Key`
    - **Body** : `multipart/form-data` avec le champ `file`
    - **Optionnel** : `client_id` pour surcharger l'ID extrait par l'OCR
    """
    # ── Validation du fichier ─────────────────────────────
    if not _allowed_file(file.filename or ""):
        raise HTTPException(
            status_code=415,
            detail=f"Extension non supportée. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (max {MAX_FILE_SIZE_MB} Mo).")

    # ── Appel OCR.space ───────────────────────────────────
    try:
        ocr_response = _call_ocr_space(file_bytes, file.filename or "upload")
    except requests.exceptions.Timeout:
        logger.error("ocr_call_failed", extra={"reason": "timeout", "client_id": current_user.id})
        OCR_FAILURES.labels(reason="timeout").inc()
        raise HTTPException(status_code=504, detail={
            "error": "Le service OCR n'a pas répondu (timeout 30 s). Réessayez.",
            "incident": "OCR_TIMEOUT",
        })
    except requests.exceptions.ConnectionError:
        logger.error("ocr_call_failed", extra={"reason": "connection_error", "client_id": current_user.id})
        OCR_FAILURES.labels(reason="connection_error").inc()
        raise HTTPException(status_code=502, detail={
            "error": "Impossible de joindre OCR.space.",
            "incident": "OCR_UNREACHABLE",
        })
    except requests.exceptions.HTTPError as e:
        logger.error("ocr_call_failed", extra={"reason": "http_error", "client_id": current_user.id, "error": str(e)})
        OCR_FAILURES.labels(reason="http_error").inc()
        raise HTTPException(status_code=502, detail={
            "error": f"OCR.space a retourné une erreur HTTP : {e}",
            "incident": "OCR_HTTP_ERROR",
        })
    except ValueError as e:
        logger.error("ocr_call_failed", extra={"reason": "processing_error", "client_id": current_user.id, "error": str(e)})
        OCR_FAILURES.labels(reason="processing_error").inc()
        raise HTTPException(status_code=422, detail={
            "error": str(e),
            "incident": "OCR_PROCESSING_ERROR",
        })

    # ── Parsing du texte ──────────────────────────────────
    raw_text = _extract_text(ocr_response)
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail={
            "error": "OCR n'a extrait aucun texte. Fichier illisible ou vide.",
            "incident": "OCR_EMPTY_RESULT",
        })

    parsed = _parse_lab_report(raw_text)

    # L'ID client vient TOUJOURS de la clé API (sécurité RGPD)
    # client_id_override sert uniquement à titre informatif / audit
    features = {k: parsed.get(k) for k in MODEL_FEATURE_ORDER}
    extra = {k: parsed.get(k) for k in ["nitrates", "nitrites", "ammonium", "chlorures", "fer", "manganese"]}

    missing = [k for k, v in features.items() if v is None]

    # ── Prédiction ML si données complètes ───────────────
    prediction_result = None
    prob_potable = None
    water_status = "Indéterminé (données manquantes)"

    if not missing:
        model = request.app.state.model
        threshold = request.app.state.best_threshold

        if model is not None:
            features_array = np.array([features[k] for k in MODEL_FEATURE_ORDER]).reshape(1, -1)
            proba = model.predict_proba(features_array)
            prob_potable = float(proba[0][1])
            prediction_result = 1 if prob_potable >= threshold else 0
            water_status = "Potable (Safe)" if prediction_result == 1 else "Non Potable (Unsafe)"

            # Persistance en base
            db = WaterFlowDB()
            db.add_prediction(
                user_id=current_user.id,
                ph=features["ph"],
                hardness=features["hardness"],
                solids=features["solids"],
                chloramines=features["chloramines"],
                sulfate=features["sulfate"],
                conductivity=features["conductivity"],
                organic_carbon=features["organic_carbon"],
                trihalomethanes=features["trihalomethanes"],
                turbidity=features["turbidity"],
                potability=prediction_result,
                source="ocr",
            )
            db.close()
        else:
            water_status = "Erreur : modèle ML indisponible"

    warnings = []
    if missing:
        warnings.append(f"{len(missing)}/9 champs absents : {', '.join(missing)}. Complétez manuellement.")

    status_code = 200 if not missing else 202
    return JSONResponse(status_code=status_code, content={
        "status": "success" if not missing else "partial_match",
        "client_id": current_user.id,
        "prediction": prediction_result,
        "probability_potable": prob_potable,
        "water_status": water_status,
        "measurement": {
            "client_id": current_user.id,
            "date_prelevement": parsed.get("date_prelevement"),
            "provenance": "OCR",
            "features": features,
            "extra_fields": extra,
        },
        "missing_features": missing,
        "warnings": warnings,
        "ocr_raw_text": raw_text,  # À retirer en production
    })


@router.get("/health", summary="Santé du service OCR")
def ocr_health():
    key_ok = OCR_SPACE_API_KEY not in ("", "helloworld")
    return {
        "ocr_service": "ocr.space",
        "api_key_configured": key_ok,
        "warning": None if key_ok else "Clé de démo active — limites : 1 page, 1 Mo, 25 000 req/mois.",
    }
