"""Carga y valida la configuración del backend desde el archivo .env."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Configuración de la app. Se lee una sola vez al arrancar."""

    def __init__(self) -> None:
        # Venice AI (proxy compatible con OpenAI que sirve modelos Claude)
        self.venice_api_key: str = os.environ.get("VENICE_API_KEY", "")
        self.venice_base_url: str = os.environ.get(
            "VENICE_BASE_URL", "https://api.venice.ai/api/v1"
        )
        self.venice_model: str = os.environ.get("VENICE_MODEL", "claude-sonnet-4-6")

        # Supabase
        self.supabase_url: str = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")
        self.supabase_service_key: str = os.environ.get("SUPABASE_SERVICE_KEY", "")

        # Cifrado de la clave de los PDFs del usuario
        self.clave_encryption_key: str = os.environ.get("CLAVE_ENCRYPTION_KEY", "")

        # Negocio
        self.admin_emails: set[str] = {
            e.strip().lower()
            for e in os.environ.get("ADMIN_EMAILS", "").split(",")
            if e.strip()
        }
        self.whatsapp_number: str = os.environ.get("WHATSAPP_NUMBER", "")

        # CORS
        self.frontend_origins: list[str] = [
            o.strip()
            for o in os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]

    def validar(self) -> list[str]:
        """Devuelve la lista de variables obligatorias que faltan."""
        faltantes = []
        obligatorias = {
            "VENICE_API_KEY": self.venice_api_key,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SERVICE_KEY": self.supabase_service_key,
            "CLAVE_ENCRYPTION_KEY": self.clave_encryption_key,
        }
        for nombre, valor in obligatorias.items():
            if not valor:
                faltantes.append(nombre)
        return faltantes


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
