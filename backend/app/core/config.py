"""Configuração da aplicação, tipada e lida do ambiente.

Segurança: segredos (SECRET_KEY, DATABASE_URL, SMTP) NÃO têm valor padrão — se
faltarem, a aplicação falha ao iniciar (fail-fast). Nada de credencial no código.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Aplicação ---
    app_name: str = "Digitalizador Bonfim Web"
    environment: str = "dev"  # dev | staging | prod
    debug: bool = False

    # --- Banco de dados (obrigatório) ---
    database_url: str  # ex.: postgresql+psycopg://user:pass@db:5432/digitalizador

    # --- Segurança / Auth (SECRET_KEY obrigatório) ---
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- 2FA / confirmação de e-mail ---
    otp_expire_minutes: int = 5
    otp_max_tentativas: int = 5
    # DEV ONLY: pula a 2ª etapa (OTP) e loga direto. Ignorado se environment=prod.
    dev_2fa_bypass: bool = False

    # --- Storage (sistema de arquivos POSIX) ---
    storage_root: str = "/data/storage"  # raiz padrão de guarda (dev/bootstrap)

    # --- CORS (origens liberadas para o frontend) ---
    cors_origins: list[str] = []
    # Regex de origem (dev): libera o frontend por IP na rede, ex.: http://192.168.0.82:5173
    cors_origin_regex: str | None = None

    # --- SMTP (envio de OTP / confirmação) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @property
    def is_prod(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # campos vêm do ambiente
