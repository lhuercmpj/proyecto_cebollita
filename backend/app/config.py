from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion compartida por la API y el simulador."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Cebollita API"
    database_url: str = "postgresql+psycopg://cebollita:cebollita_dev@localhost:5433/cebollita"
    app_api_key: str = Field(default="change-me", min_length=1)
    sensor_api_key: str = Field(default="change-me-too", min_length=1)
    sensor_device_url: str = "http://localhost:8081"
    # El firmware toma 30 muestras separadas por 300 ms (unos 9 s), por lo que
    # 10 s dejaba muy poco margen para la red y la serializacion.
    sensor_timeout_seconds: float = Field(default=20.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

