from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    PROCESS_COUNT: int = 4
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    PROJECT_ROOT: Path = BASE_DIR.parent
    
    PROCESS_CONFIG_PATH: str = str(PROJECT_ROOT / "config" / "processes.json")
    NETWORK_CONFIG_PATH: str = str(PROJECT_ROOT / "config" / "network.json")
    SNAPSHOTS_DIR: str = str(PROJECT_ROOT / "snapshots")
    LOGS_DIR: str = str(PROJECT_ROOT / "logs")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
