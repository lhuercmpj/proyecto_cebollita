from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion compartida por la API, el simulador, el bot y el programador."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Cebollita API"
    plant_id: str = "cebollita"
    timezone: str = "America/Montevideo"
    database_url: str = "postgresql+psycopg://cebollita:cebollita_dev@localhost:5433/cebollita"
    sensor_device_url: str = "http://localhost:8081"
    # El firmware toma 30 muestras separadas por 300 ms (unos 9 s), por lo que
    # 10 s dejaba muy poco margen para la red y la serializacion.
    sensor_timeout_seconds: float = Field(default=20.0, gt=0)

    # --- Medicion y reportes periodicos -------------------------------------
    report_interval_minutes: float = Field(default=30, gt=0)
    # Una lectura se considera atrasada si supera el intervalo mas este margen.
    stale_margin_minutes: float = Field(default=10, ge=0)
    # Tiempo minimo antes de repetir una alerta del mismo estado.
    alert_repeat_minutes: float = Field(default=180, gt=0)

    # --- Telegram -------------------------------------------------------------
    telegram_bot_token: str = ""
    # Destinatario fijo opcional, ademas de los chats que hagan /start.
    telegram_chat_id: str = ""
    # Lista opcional de chat_id separados por coma que pueden suscribirse.
    # Vacia = cualquiera que haga /start puede suscribirse (prototipo).
    telegram_allowed_chat_ids: str = ""

    # --- Gemini ---------------------------------------------------------------
    gemini_api_key: str = ""
    # Alias que apunta al Flash estable vigente. Se puede fijar una version.
    gemini_model: str = "gemini-flash-latest"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    gemini_temperature: float = Field(default=0.7, ge=0, le=2)

    # --- RAG ------------------------------------------------------------------
    references_dir: str = "data/references"
    rag_top_k: int = Field(default=4, ge=1, le=20)
    chat_history_turns: int = Field(default=6, ge=0, le=30)

    @property
    def allowed_chat_ids(self) -> set[str]:
        return {
            item.strip()
            for item in self.telegram_allowed_chat_ids.split(",")
            if item.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
