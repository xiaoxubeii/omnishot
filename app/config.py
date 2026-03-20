from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "AI Phantom Studio Demo"
    host: str = "0.0.0.0"
    port: int = 8000
    public_base_url: str | None = None

    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_ws_url: str = "ws://127.0.0.1:8188/ws"

    workflow_template: Path = ROOT_DIR / "workflows/flux_product_demo.template.json"
    workflow_bindings: Path = ROOT_DIR / "workflows/flux_product_demo.bindings.json"
    python_bin: Path = ROOT_DIR / ".venv" / "bin" / "python"
    catvton_script: Path = ROOT_DIR / "scripts" / "run_catvton_tryon.py"
    catvton_root: Path = ROOT_DIR.parent / "CatVTON"
    qwen_edit_model_id: str = "Qwen/Qwen-Image-Edit-2511"
    qwen_edit_lightning_repo: str = "lightx2v/Qwen-Image-Lightning"
    qwen_edit_lightning_filename: str = "Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors"
    qwen_edit_angle_lora_repo: str = "dx8152/Qwen-Edit-2509-Multiple-angles"
    qwen_edit_angle_lora_filename: str = "镜头转换.safetensors"
    qwen_edit_cache_dir: Path = ROOT_DIR / "data" / "hf-cache"
    qwen_edit_timeout_seconds: int = 3600
    qwen_edit_default_steps: int = 8
    qwen_edit_default_true_cfg_scale: float = 1.0
    qwen_edit_default_width: int = 1024
    qwen_edit_default_height: int = 1024
    qwen_edit_default_max_side: int = 1024
    qwen_edit_cpu_offload: bool = True
    qwen_edit_enable_lightning: bool = False
    qwen_edit_enable_angle_lora: bool = False

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
        "qwen_edit_cache_dir",
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
    settings.qwen_edit_cache_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    return settings
