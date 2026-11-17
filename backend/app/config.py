"""Configuración leída de variables de entorno (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    oracle_password: str = ""

    lab_db_host: str = "localhost"
    lab_db_port: int = 1521
    lab_db_service: str = "FREEPDB1"
    lab_db_user: str = "LAB"
    lab_db_password: str = ""
    lab_auto_seed: bool = True
    lab_allow_reset: bool = True

    admin_enabled: bool = True
    admin_db_user: str = "SYSTEM"
    admin_db_password: str = ""

    external_db_dsn: str = ""
    external_db_user: str = ""
    external_db_password: str = ""
    external_db_allow_write: bool = False

    max_rows: int = 500
    query_timeout_seconds: int = 60
    session_idle_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def lab_dsn(self) -> str:
        return f"{self.lab_db_host}:{self.lab_db_port}/{self.lab_db_service}"

    @property
    def admin_password(self) -> str:
        return self.admin_db_password or self.oracle_password

    @property
    def external_configured(self) -> bool:
        return bool(self.external_db_dsn and self.external_db_user)


@lru_cache
def get_settings() -> Settings:
    return Settings()
