"""Agrega os routers da API v1."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    cadastros,
    certificados,
    documentos,
    health,
    parametros,
    registros,
    usuarios,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(certificados.router)
api_router.include_router(documentos.router)
api_router.include_router(registros.router)
api_router.include_router(cadastros.router)
api_router.include_router(parametros.router)

# Próximo: assinatura multipartes (substituição do ZapSign)
