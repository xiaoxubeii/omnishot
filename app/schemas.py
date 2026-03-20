from typing import Literal

from pydantic import BaseModel, Field


class GenerateJsonRequest(BaseModel):
    prompt: str = Field(min_length=1)
    image_base64: str = Field(min_length=1)
    negative_prompt: str = ""
    seed: int | None = None
    filename: str | None = None


class TryOnJsonRequest(BaseModel):
    image_base64: str = Field(min_length=1)
    person_image_base64: str | None = None
    filename: str | None = None
    person_filename: str | None = None
    person_template: str = "woman_1"
    cloth_type: Literal["upper", "lower", "overall"] = "overall"
    seed: int = 42
    steps: int = 30
    guidance: float = 2.5
    width: int = 768
    height: int = 1024


class EditJsonRequest(BaseModel):
    image_base64: str = Field(min_length=1)
    style_reference_images_base64: list[str] = Field(default_factory=list)
    angle_reference_images_base64: list[str] = Field(default_factory=list)
    prompt: str = ""
    negative_prompt: str = ""
    filename: str | None = None
    seed: int = 123
    width: int | None = None
    height: int | None = None
    steps: int = 8
    true_cfg_scale: float = 1.0
    angle_preset: str | None = None
    use_angle_lora: bool = False
    angle_lora_scale: float = 1.0
    use_lightning: bool = False
    lightning_lora_scale: float = 1.0


class ReferenceSceneJsonRequest(BaseModel):
    image_base64: str = Field(min_length=1)
    style_reference_images_base64: list[str] = Field(default_factory=list)
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    filename: str | None = None
    seed: int = 123
    width: int | None = None
    height: int | None = None
    steps: int = 8
    true_cfg_scale: float = 1.0
    shadow_strength: float = 0.4
    reflection_strength: float = 0.14
    color_harmonize_strength: float = 0.18


class GenerateResponse(BaseModel):
    prompt_id: str
    pipeline: str = "scene"
    generator_mode: str
    filename: str
    output_url: str
    mime_type: str
    image_base64: str
    comfyui_prompt_id: str | None = None
    local_input_path: str | None = None
    metadata: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    comfyui_reachable: bool
    mock_fallback_enabled: bool
    workflow_template_exists: bool
    workflow_bindings_exists: bool
    workflow_nodes: int | None = None
    workflow_binding_errors: list[str] = Field(default_factory=list)
    tryon_script_exists: bool = False
    tryon_root_exists: bool = False
    tryon_template_count: int = 0
    edit_preset_count: int = 0
    qwen_edit_model_id: str
    qwen_edit_model_cached: bool = False
    qwen_edit_model_ready: bool = False
    qwen_edit_cache_issues: list[str] = Field(default_factory=list)
    comfyui_details: dict = Field(default_factory=dict)
