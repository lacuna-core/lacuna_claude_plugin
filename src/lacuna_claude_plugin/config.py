from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LACUNA_", env_file=".env", extra="ignore", frozen=True
    )

    request_timeout: float = 30.0
    log_level: str = "INFO"


SETTINGS = Settings()
