from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Central runtime settings loaded from env and defaults.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_json_path: Path | None = None  # default data/app_data.json
    ml_weight: float = 0.6
    rule_weight: float = 0.4
    # training/evaluate.py overwrites the next two lines
    tier_safe_max: float = 0.35
    tier_suspicious_max: float = 0.65
    artifacts_dir: Path = Path(__file__).resolve().parent / "ml_artifacts"

settings = Settings()
