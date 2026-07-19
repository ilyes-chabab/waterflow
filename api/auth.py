"""
auth.py - Dépendance d'authentification partagée (Waterflow 2)
Utilisée dans main.py ET ocr_router.py via Depends(get_current_user).
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from data.db.WaterFlowDB import WaterFlowDB

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class UserInfo:
    id: int
    username: str
    role: str
    expires_at: str | None = None


def get_current_user(api_key: str | None = Security(api_key_header)) -> UserInfo:
    """
    Dépendance FastAPI : valide la clé API et retourne l'utilisateur.
    À injecter avec Depends(get_current_user) dans n'importe quelle route.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante (header X-API-Key requis).",
        )

    hashed = hashlib.sha256(api_key.encode()).hexdigest()

    try:
        db = WaterFlowDB()
        all_users = db.get_users()
        db.close()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'accès base de données : {e}",
        )

    # Structure attendue : (user_id, username, api_key_hash, role, ...)
    matched = next((u for u in all_users if u[2] == hashed), None)
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou expirée.",
        )
    
    if len(matched) > 4 and matched[4] == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette clé API a été révoquée.",
        )

    expires_at = matched[5] if len(matched) > 5 else None
    if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cette clé API a expiré. Merci de la renouveler via /api/renew-key.",
        )

    return UserInfo(id=matched[0], username=matched[1], role=matched[3], expires_at=expires_at)


def require_role(*allowed_roles: str):
    """
    Fabrique de dépendance : vérifie que l'utilisateur a l'un des rôles autorisés.

    Usage dans une route :
        @router.get("/admin")
        def admin_route(user = Depends(require_role("Admin", "Quality_Analyst"))):
            ...
    """
    def _check(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôles autorisés : {', '.join(allowed_roles)}.",
            )
        return current_user

    return _check
