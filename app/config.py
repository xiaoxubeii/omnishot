from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "AI Phantom Studio Demo"
    host: str = "0.0.0.0"
    port: int = 8000

    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_ws_url: str = "ws://127.0.0.1:8188/ws"

    workflow_template: Path = ROOT_DIR / "workflows/flux_product_demo.template.json"
    workflow_bindings: Path = ROOT_DIR / "workflows/flux_product_demo.bindings.json"
    python_bin: Path = ROOT_DIR / ".venv" / "bin" / "python"
    catvton_script: Path = ROOT_DIR / "scripts" / "run_catvton_tryon.py"
    catvton_root: Path = ROOT_DIR.parent / "CatVTON"

    upload_dir: Path = ROOT_DIR / "data" / "input"
    output_dir: Path = ROOT_DIR / "data" / "output"

    generation_timeout_seconds: int = 900
    tryon_timeout_seconds: int = 1800
    hf_endpoint: str = "https://hf-mirror.com"
    mock_fallback_enabled: bool = True
    mock_delay_seconds: float = 1.0

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "workflow_template",
        "workflow_bindings",
        "python_bin",
        "catvton_script",
        "catvton_root",
        "upload_dir",
        "output_dir",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser()


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    return settings
