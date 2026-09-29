"""Endpoints de saúde (liveness / readiness)."""
from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    """Liveness: o processo está de pé."""
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "environment": s.environment}


@router.get("/health/ready")
def ready(db: SessionDep, response: Response) -> dict[str, str]:
    """Readiness: o banco responde."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - readiness reporta qualquer falha de banco
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": "down"}
    return {"status": "ok", "database": "up"}
