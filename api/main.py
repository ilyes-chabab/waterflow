"""
main.py - Application FastAPI principale Waterflow 2
Modules : Prédiction + Données + OCR
Lancement : uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Swagger UI : http://localhost:8000/docs
"""

import hashlib
import os
import secrets
import numpy as np
import mlflow.xgboost
import time
from contextlib import asynccontextmanager
from mlflow.tracking import MlflowClient
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from data.db.WaterFlowDB import WaterFlowDB
from .auth import UserInfo, get_current_user, require_role
from .logging_config import logger
from .ocr_router import router as ocr_router

# Metriques RED (Rate, Errors, Duration) exposees sur /metrics pour Prometheus.
HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "Request duration", ["endpoint"]
)

limiter = Limiter(key_func=get_remote_address)


# ──────────────────────────────────────────────
# Lifespan : chargement du modèle au démarrage
# (remplace @app.before_first_request de Flask)
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle MLflow une seule fois au démarrage."""
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
    model_uri = "models:/water_quality_model/Production"
    try:
        logger.info("model_loading", extra={"model_uri": model_uri})
        app.state.model = mlflow.xgboost.load_model(model_uri)
        app.state.best_threshold = 0.37
        logger.info("model_loaded", extra={"model_uri": model_uri})
    except Exception as e:
        logger.error("model_load_failed", extra={"model_uri": model_uri, "error": str(e)})
        app.state.model = None
        app.state.best_threshold = 0.37
    yield  # L'application tourne ici
    # (nettoyage éventuel au shutdown)


# ──────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────
app = FastAPI(
    title="Waterflow 2 API",
    description="Plateforme MLOps de classification de la potabilité de l'eau.",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(ocr_router)

# Expose les metriques Prometheus (RATE/ERRORS/DURATION) sur GET /metrics,
# scrapees par le service `prometheus` du docker-compose (voir prometheus.yml).
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    duration = time.time() - t0

    HTTP_LATENCY.labels(endpoint=request.url.path).observe(duration)
    HTTP_REQUESTS.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    return response


# Pas de CORSMiddleware : l'UI Streamlit appelle cette API cote serveur (module
# `requests`), jamais depuis du JS execute dans un navigateur. Sans CORSMiddleware,
# FastAPI n'ajoute aucun header Access-Control-Allow-Origin, ce qui est deja la
# posture la plus restrictive (un navigateur bloque par defaut toute lecture
# cross-origin en JS). A revoir uniquement si un front web tiers doit un jour
# appeler cette API directement depuis un navigateur.


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Ajoute des en-tetes de securite de base a chaque reponse."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - t0
    
    if request.url.path in ("/health", "/api/ocr/health", "/metrics"):
        return response

    user_id = None
    api_key = request.headers.get("X-API-Key")
    
    if api_key:
        try:
            hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
            
            db = WaterFlowDB()
            all_users = db.get_users()
            db.close()
            
            matched = next((u for u in all_users if u[2] == hashed_key), None)
            if matched:
                user_id = matched[0]
        except Exception:
            user_id = None

    try:
        db = WaterFlowDB()
        db.add_audit_log(
            user_id=user_id,
            endpoint=request.url.path,
            method=request.method,
            status=response.status_code,
            duration=round(duration, 4),
            ip=request.client.host if request.client else "unknown"
        )
        db.close()
    except Exception as e:
        logger.error("audit_log_write_failed", extra={"error": str(e)})

    return response


# ──────────────────────────────────────────────
# Schémas Pydantic  (validation automatique)
# ──────────────────────────────────────────────
class FeaturesPayload(BaseModel):
    features: list[float] = Field(
        ...,
        min_length=9,
        max_length=9,
        description="9 mesures physico-chimiques dans l'ordre : ph, hardness, solids, "
                    "chloramines, sulfate, conductivity, organic_carbon, trihalomethanes, turbidity",
        examples=[[7.0, 204.8, 20791.3, 7.3, 368.5, 564.3, 10.3, 86.9, 2.9]],
    )


class CreateClientPayload(BaseModel):
    username: str = Field(..., min_length=1, description="Nom du client ou de la structure")
    role: str = Field("Client", description="Rôle : Client, Quality_Analyst, Admin")


# ──────────────────────────────────────────────
# Helpers MLflow
# ──────────────────────────────────────────────
MODEL_NAME = "water_quality_model"


def _get_model_metrics() -> dict | None:
    client = MlflowClient()
    versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    if not versions:
        return None
    v = versions[0]
    run = client.get_run(v.run_id)
    return {
        "version": v.version,
        "run_id": v.run_id,
        "stage": v.current_stage,
        "metrics": run.data.metrics,
        "params": run.data.params,
    }


def _get_all_model_versions() -> list[dict]:
    client = MlflowClient()
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    result = []
    for v in versions:
        try:
            run = client.get_run(v.run_id)
            metrics, params = run.data.metrics, run.data.params
        except Exception:
            metrics, params = {}, {}
        result.append({
            "version": v.version,
            "stage": v.current_stage,
            "run_id": v.run_id,
            "metrics": metrics,
            "params": params,
        })
    result.sort(key=lambda x: int(x["version"]), reverse=True)
    return result


def _predict_with_run(run_id: str, features_list: list[float], threshold: float) -> tuple[int, float]:
    versioned_model = mlflow.xgboost.load_model(f"runs:/{run_id}/model")
    arr = np.array(features_list).reshape(1, -1)
    proba = versioned_model.predict_proba(arr)
    prob = float(proba[0][1])
    return (1 if prob >= threshold else 0), prob


# ──────────────────────────────────────────────
# Routes – Santé
# ──────────────────────────────────────────────
@app.get("/health", tags=["Système"])
def health(request: Request):
    return {"status": "healthy", "model_loaded": request.app.state.model is not None}


# ──────────────────────────────────────────────
# Routes – Authentification
# ──────────────────────────────────────────────
@app.post("/api/login", tags=["Auth"], summary="Verifier sa cle API")
@limiter.limit("10/minute")
def login(request: Request, current_user: Annotated[UserInfo, Depends(get_current_user)]):
    """Verifie la cle API et retourne les infos de l'utilisateur."""
    return {
        "authenticated": True,
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }


# ──────────────────────────────────────────────
# Routes – Prélèvements (Measurements)
# ──────────────────────────────────────────────
@app.post("/api/measurements", status_code=201, tags=["Prélèvements"],
          summary="Soumettre un prelèvement et obtenir une prediction")
@limiter.limit("500/hour")
def add_measurement(
    payload: FeaturesPayload,
    request: Request,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
):
    model = request.app.state.model
    threshold = request.app.state.best_threshold

    if model is None:
        raise HTTPException(status_code=503, detail="Modèle ML indisponible.")

    f = payload.features
    arr = np.array(f).reshape(1, -1)
    proba = model.predict_proba(arr)
    prob = float(proba[0][1])
    pred = 1 if prob >= threshold else 0
    status_label = "Potable (Safe)" if pred == 1 else "Non Potable (Unsafe)"

    db = WaterFlowDB()
    db.add_prediction(
        user_id=current_user.id,
        ph=f[0], hardness=f[1], solids=f[2], chloramines=f[3],
        sulfate=f[4], conductivity=f[5], organic_carbon=f[6],
        trihalomethanes=f[7], turbidity=f[8],
        potability=pred, source="manuel",
    )
    db.close()

    return {
        "client_id": current_user.id,
        "prediction": pred,
        "probability_potable": prob,
        "water_status": status_label,
        "msg": "Prelèvement et prediction sauvegardes avec succès.",
    }


@app.get("/api/measurements", tags=["Prélèvements"],
         summary="Historique de mes prélèvements (client)")
def get_client_measurements(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
):
    db = WaterFlowDB()
    rows = db.get_predictions_by_user(current_user.id)
    db.close()

    history = [{
        "id_prediction": r[0],
        "measures": {
            "ph": r[2], "hardness": r[3], "solids": r[4],
            "chloramines": r[5], "sulfate": r[6], "conductivity": r[7],
            "organic_carbon": r[8], "trihalomethanes": r[9], "turbidity": r[10],
        },
        "potability_result": r[11],
    } for r in rows]

    return {
        "client_id": current_user.id,
        "username": current_user.username,
        "total_records": len(history),
        "history": history,
    }


# ──────────────────────────────────────────────
# Routes – Clients (Admin)
# ──────────────────────────────────────────────
@app.post("/api/clients", status_code=201, tags=["Clients"],
          summary="Créer un client (Admin uniquement)")
def create_client(
    payload: CreateClientPayload,
    current_user: Annotated[UserInfo, Depends(require_role("Admin"))],
):
    plain_key = secrets.token_hex(32)
    hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()

    db = WaterFlowDB()
    db.add_user(username=payload.username, api_key=hashed_key, right=payload.role)
    all_users = db.get_users()
    db.close()

    new_user = next((u for u in all_users if u[2] == hashed_key), None)

    return {
        "message": "Client cree avec succès.",
        "client": {
            "id": new_user[0] if new_user else "inconnu",
            "username": payload.username,
            "role": payload.role,
            "api_key_plain": plain_key,  # Affiché UNE SEULE FOIS — ne pas stocker côté serveur
        },
    }


@app.get("/api/clients", tags=["Clients"],
         summary="Lister tous les clients (Admin uniquement)")
def list_clients(
    current_user: Annotated[UserInfo, Depends(require_role("Admin"))],
):
    db = WaterFlowDB()
    all_users = db.get_users()
    db.close()

    return {
        "total_clients": len(all_users),
        "clients": [
            {"id": u[0], "username": u[1], "api_key_hash": u[2], "role": u[3]}
            for u in all_users
        ],
    }

@app.post("/api/clients/{cid}/rotate-key", tags=["Clients"],
          summary="Révoquer et régénérer la clé API d'un client (Admin uniquement)")
def rotate_client_key(
    cid: int,
    current_user: Annotated[UserInfo, Depends(require_role("Admin"))],
):
    # 1. Génération de la nouvelle clé (comme à la création)
    plain_key = secrets.token_hex(32)
    hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()

    db = WaterFlowDB()
    all_users = db.get_users()
    
    # Vérifier si le client existe vraiment
    client_exists = any(u[0] == cid for u in all_users)
    if not client_exists:
        db.close()
        raise HTTPException(status_code=404, detail="Client introuvable.")

    # 2. Révocation de l'ancienne + Injection de la nouvelle clé en DB
    db.rotate_user_key(user_id=cid, new_hashed_key=hashed_key)
    db.close()

    # 3. Retour de la clé brute UNE SEULE FOIS
    return {
        "message": "La clé précédente a été révoquée. Voici la nouvelle clé API.",
        "client_id": cid,
        "api_key_plain": plain_key  # À copier immédiatement, ne sera plus jamais accessible !
    }

@app.get("/api/audit-logs", tags=["Admin"])
def get_all_audit_logs(
    current_user: Annotated[UserInfo, Depends(require_role("Admin"))]
):
    db = WaterFlowDB()
    raw_logs = db.get_audit_logs()
    db.close()

    formatted_logs = []
    for log in raw_logs:
        formatted_logs.append({
            "id": log[0],
            "user_id": log[1],
            "endpoint": log[2],
            "method": log[3],
            "status": log[4],
            "duration": log[5],
            "ip": log[6],
            "created_at": log[7]
        })

    return {
        "total_logs": len(formatted_logs),
        "logs": formatted_logs
    }
# ──────────────────────────────────────────────
# Routes – RGPD
# ──────────────────────────────────────────────
@app.get("/api/me", tags=["RGPD"], summary="Mes données personnelles (droit d'accès RGPD)")
def rgpd_info(current_user: Annotated[UserInfo, Depends(get_current_user)]):
    return {
        "declaration": "Conformément au RGPD, voici vos données stockées.",
        "donnees_personnelles": {
            "id_client": current_user.id,
            "nom_utilisateur": current_user.username,
            "role": current_user.role,
        },
        "regle_conservation": (
            "Les mesures de prélèvements anonymisées sont conservées 5 ans. "
            "Vos données d'identification sont supprimées à la clôture du compte."
        ),
    }

@app.delete("/api/me", tags=["RGPD"])
def delete_my_account(current_user: Annotated[UserInfo, Depends(get_current_user)]):
    db = WaterFlowDB()
    db.delete_user(current_user.id)
    db.close()
    return {"message": "Compte et données supprimés."}

# ──────────────────────────────────────────────
# Routes – Dashboard (Analyste / Admin)
# ──────────────────────────────────────────────
@app.get("/api/dashboard/measurements", tags=["Dashboard"],
         summary="Tous les prélèvements avec filtres (Analyste/Admin)")
def dashboard_measurements(
    current_user: Annotated[UserInfo, Depends(require_role("Quality_Analyst", "Admin"))],
    client_id: int | None = None,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    zone: str | None = None,
):
    db = WaterFlowDB()
    rows = db.get_all_predictions_filtered(
        client_id=client_id, source=source,
        date_from=date_from, date_to=date_to, zone=zone,
    )
    db.close()

    data = [{
        "id_prediction": r[0],
        "client": {"id": r[1], "username": r[2], "role": r[3]},
        "measures": {
            "ph": r[4], "hardness": r[5], "solids": r[6],
            "chloramines": r[7], "sulfate": r[8], "conductivity": r[9],
            "organic_carbon": r[10], "trihalomethanes": r[11], "turbidity": r[12],
        },
        "potability_result": r[13],
        "source": r[14],
        "created_at": r[15],
    } for r in rows]

    return {"total_records": len(data), "data": data}


@app.get("/api/dashboard/metrics", tags=["Dashboard"],
         summary="Métriques du modèle en Production (Analyste/Admin)")
def dashboard_metrics(
    current_user: Annotated[UserInfo, Depends(require_role("Quality_Analyst", "Admin"))],
):
    metrics = _get_model_metrics()
    if metrics is None:
        raise HTTPException(status_code=404, detail="Aucune version 'Production' trouvée sur MLflow.")
    return metrics


@app.get("/api/dashboard/model-versions", tags=["Dashboard"],
         summary="Toutes les versions du modèle (Analyste/Admin)")
def dashboard_model_versions(
    current_user: Annotated[UserInfo, Depends(require_role("Quality_Analyst", "Admin"))],
):
    versions = _get_all_model_versions()
    return {"total_versions": len(versions), "versions": versions}


class ReplayPayload(BaseModel):
    run_id: str = Field(..., description="run_id MLflow de la version à rejouer")
    features: list[float] = Field(..., min_length=9, max_length=9)


@app.post("/api/dashboard/replay", tags=["Dashboard"],
          summary="Rejouer une prédiction avec une version précise du modèle (Analyste/Admin)")
def dashboard_replay(
    payload: ReplayPayload,
    request: Request,
    current_user: Annotated[UserInfo, Depends(require_role("Quality_Analyst", "Admin"))],
):
    threshold = request.app.state.best_threshold
    pred, prob = _predict_with_run(payload.run_id, payload.features, threshold)
    return {
        "run_id": payload.run_id,
        "prediction": pred,
        "probability_potable": prob,
        "water_status": "Potable (Safe)" if pred == 1 else "Non Potable (Unsafe)",
    }
