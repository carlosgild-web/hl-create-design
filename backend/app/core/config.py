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
    llm_provider: Literal["auto", "demo", "ollama", "groq", "dahl", "fake"] = "auto"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_timeout_s: float = Field(default=180.0, gt=0, le=3600)  # per model call
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Dahl inference: OpenAI-compatible, first in the auto chain (decision 0029). GLM-5.3
    # Flash was the one model of the three that answered a real turn with a native tool call.
    dahl_api_key: SecretStr | None = None
    dahl_model: str = "zai-org/GLM-5.3-Flash"
    dahl_base_url: str = "https://inference.dahl.global/v1"

    # Mock SAP
    sap_base_url: str = "http://localhost:8100"
    sap_user: str = "demo"
    sap_password: SecretStr = SecretStr("demo")

    # KiCad
    kicad_cli: str = "kicad-cli"
    # "Open in KiCad" starts the GUI next to kicad-cli on the backend's machine: only useful
    # when that is the user's own computer (local mode). The Docker image turns it off.
    kicad_open_enabled: bool = True

    # Storage
    designs_root: Path = Path("./data/designs")
    data_dir: Path = Path("./data")

    # Agent
    agent_max_iterations: int = Field(default=6, ge=1, le=20)
    # One whole answer (all model calls and rate-limit waits); then the turn ends with a message.
    agent_turn_timeout_s: float = Field(default=120.0, gt=0, le=3600)
    # The backend searches the manual itself before the first model call (decision 0024):
    # auto = for questions about the rules or the app, on = for every message, off = never.
    agent_preretrieval: Literal["auto", "on", "off"] = "auto"
    # Ollama only: add one short example answer to the system prompt (decision 0026).
    agent_few_shot: bool = False

    # The built frontend (`npm run build`); served at `/` when the folder exists (Docker image).
    frontend_dir: Path = Path("./frontend/dist")

    # Public demo safety (0 = off, the default for local use)
    rate_limit_per_min: int = Field(default=0, ge=0)  # state-changing requests per IP per minute
    daily_token_cap: int = Field(default=0, ge=0)  # model tokens per UTC day, all users together
    designs_ttl_hours: int = Field(default=0, ge=0)  # delete design folders older than this
    trust_forwarded_for: bool = False  # take the client IP from X-Forwarded-For (behind a proxy)

    @field_validator("designs_root", "data_dir", "frontend_dir")
    @classmethod
    def _relative_to_repo(cls, path: Path) -> Path:
        """`./data` means the repo's data folder, whatever the working directory is."""
        return path if path.is_absolute() else REPO_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """The process-wide settings (cached; tests build their own `Settings`)."""
    return Settings()
