from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # --- Pfade --- #
    data_dir: Path = BASE_DIR / "data"
    testset_dir: Path = data_dir / "testset"
    uploads_dir: Path = data_dir / "uploads"
    markdown_cache_dir: Path = data_dir / "markdown_cache"

    # --- PostgreSQL --- #
    DB_NAME: str = "docclass"
    DB_USER: str = "postgres"
    DB_PASSWORD: SecretStr = SecretStr("")
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    # --- Pipeline --- #
    ocr_enabled: bool = True
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: SecretStr | None = None  # nur für die LLM-Extraktion nötig

    # --- Evaluation --- #
    mlflow_tracking_uri: str = "http://localhost:5000"  # docker compose up -d mlflow

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:
        # URL.create maskiert Sonderzeichen im Passwort korrekt.
        return URL.create(
            "postgresql+psycopg",
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value(),
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )


settings = Settings()
