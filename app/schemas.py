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
    comfyui_details: dict = Field(default_factory=dict)
