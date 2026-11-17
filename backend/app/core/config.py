"""Application settings, read from environment variables (and the repo's `.env`).

Every configurable value lives here; `.env.example` documents the same names.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repo root is three levels above `app/`.
REPO_ROOT = Path(__file__).resolve().parents[3]
# The Design Manual (ES and EN) that the assistant searches and cites.
MANUAL_DIR = REPO_ROOT / "docs" / "manual"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: Literal["fake", "ollama", "anthropic"] = "fake"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    # Mock SAP
    sap_base_url: str = "http://localhost:8100"
    sap_user: str = "demo"
    sap_password: SecretStr = SecretStr("demo")

    # KiCad
    kicad_cli: str = "kicad-cli"

    # Storage
    designs_root: Path = Path("./data/designs")
    data_dir: Path = Path("./data")

    # Agent
    agent_max_iterations: int = Field(default=6, ge=1, le=20)

    @field_validator("designs_root", "data_dir")
    @classmethod
    def _relative_to_repo(cls, path: Path) -> Path:
        """`./data` means the repo's data folder, whatever the working directory is."""
        return path if path.is_absolute() else REPO_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """The process-wide settings (cached; tests build their own `Settings`)."""
    return Settings()
