"""Configuration Management with Pydantic Settings."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings.

    Lädt Konfiguration aus Environment Variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI / LLM
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"

    # Database
    postgres_connection_string: Optional[str] = None

    # CRM (PIPEDRIVE)
    pipedrive_api_key: Optional[str] = None
    pipedrive_domain: Optional[str] = None

    # SAIA 3D Measurement
    saia_api_key: Optional[str] = None
    saia_api_url: Optional[str] = None

    # Application
    environment: str = "development"
    log_level: str = "INFO"


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings instance
    """
    return Settings()
