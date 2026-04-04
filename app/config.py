from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Chats / moderation queue (JSON file). Override with DATA_JSON_PATH.
    data_json_path: Path | None = None
    ml_weight: float = 0.6
    rule_weight: float = 0.4
    # --- begin auto tier thresholds (training/evaluate.py) ---
    tier_safe_max: float = 0.35
    tier_suspicious_max: float = 0.65
    # --- end auto tier thresholds ---
    artifacts_dir: Path = Path(__file__).resolve().parent / "ml_artifacts"

settings = Settings()
