import asyncio
import base64
import io
import json
import mimetypes
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.cloth_preprocessor import composite_foreground_locked, extract_cutout_rgba, preprocess_cloth_image
from app.comfy_client import ComfyClient
from app.config import ROOT_DIR, get_settings
from app.edit_runner import run_qwen_edit
from app.presets import CATALOG_PROFILES, EDIT_PRESETS, SCENE_PRESETS
from app.reference_scene_pipeline import build_neutral_product_preview, composite_reference_scene
from app.reference_style_cleanup import prepare_style_reference_images
from app.schemas import (
    EditJsonRequest,
    GenerateJsonRequest,
    GenerateResponse,
    HealthResponse,
    ReferenceSceneJsonRequest,
    TryOnJsonRequest,
)
from app.tryon_runner import run_catvton_tryon
from app.tryon_templates import list_tryon_templates
from app.workflow import build_workflow, inspect_workflow


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/outputs", StaticFiles(directory=str(settings.output_dir)), name="outputs")


MAX_EDIT_REFERENCE_IMAGES = 2
MAX_REFERENCE_SCENE_STYLE_IMAGES = 4
DEFAULT_EDIT_NEGATIVE_PROMPT = (
    "不同商品，商品主体改变，版型改变，颜色改变，花纹改变，面料改变，材质改变，"
    "长度改变，领口改变，袖型改变，肩带改变，蕾丝改变，纽扣改变，logo改变，"
    "多余配饰，重复商品，多个商品，几何错误，结构损坏，模糊，低质量，水印，文字"
)
DEFAULT_REFERENCE_SCENE_NEGATIVE_PROMPT = (
    "不同商品，商品主体改变，商品缺失，商品位置大幅漂移，商品比例改变，颜色改变，"
    "花纹改变，面料改变，材质改变，轮廓改变，辅料改变，多个商品，人物上身，手持商品，"
    "背景脏乱，透视混乱，结构错误，边缘破损，低质量，模糊，水印，文字"
)


def _build_output_url(filename: str) -> str:
    relative = f"/outputs/{filename}"
    if settings.public_base_url and settings.public_base_url.strip():
        return f"{settings.public_base_url.rstrip('/')}{relative}"
    return relative


@app.on_event("startup")
async def startup_event() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    app.state.comfy = ComfyClient(settings.comfyui_base_url, settings.comfyui_ws_url)
    app.state.gpu_lock = asyncio.Lock()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await app.state.comfy.aclose()


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(ROOT_DIR / "demo.html")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    workflow_info = inspect_workflow(settings.workflow_template, settings.workflow_bindings)
    comfyui_reachable = False
    comfyui_details: dict = {}
    qwen_edit_model_ready, qwen_edit_cache_issues = _inspect_hf_repo_cache(
        settings.qwen_edit_cache_dir,
        settings.qwen_edit_model_id,
    )

    try:
        comfyui_details = await app.state.comfy.health()
        comfyui_reachable = True
    except Exception as exc:
        comfyui_details = {"error": str(exc)}

    return HealthResponse(
        status="ok",
        comfyui_reachable=comfyui_reachable,
        mock_fallback_enabled=settings.mock_fallback_enabled,
        workflow_template_exists=workflow_info["workflow_template_exists"],
        workflow_bindings_exists=workflow_info["workflow_bindings_exists"],
        workflow_nodes=workflow_info["workflow_nodes"],
        workflow_binding_errors=workflow_info["workflow_binding_errors"],
        tryon_script_exists=settings.catvton_script.exists(),
        tryon_root_exists=settings.catvton_root.exists(),
        tryon_template_count=len(list_tryon_templates()),
        edit_preset_count=len(EDIT_PRESETS),
        qwen_edit_model_id=settings.qwen_edit_model_id,
        qwen_edit_model_cached=qwen_edit_model_ready,
        qwen_edit_model_ready=qwen_edit_model_ready,
        qwen_edit_cache_issues=qwen_edit_cache_issues,
        comfyui_details=comfyui_details,
    )


@app.get("/api/presets/scenes")
async def get_scene_presets() -> list[dict]:
    return SCENE_PRESETS


@app.get("/api/presets/edit-presets")
async def get_edit_presets() -> list[dict]:
    return EDIT_PRESETS


@app.get("/api/presets/catalog-profiles")
async def get_catalog_profiles() -> list[dict]:
    return CATALOG_PROFILES


@app.get("/api/presets/tryon-templates")
async def get_tryon_templates() -> list[dict]:
    return list_tryon_templates()


@app.post("/generate", response_model=GenerateResponse)
@app.post("/generate/scene", response_model=GenerateResponse)
async def generate_scene(request: Request) -> GenerateResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        incoming = await _parse_json_request(request)
    elif content_type.startswith("multipart/form-data"):
        incoming = await _parse_multipart_request(request)
    else:
        raise HTTPException(status_code=415, detail="Use multipart/form-data or application/json")

    input_path = _persist_input(incoming["image_bytes"], incoming["filename"])

    try:
        async with app.state.gpu_lock:
            return await _generate_with_comfy(
                image_bytes=incoming["image_bytes"],
                filename=incoming["filename"],
                prompt=incoming["prompt"],
                negative_prompt=incoming["negative_prompt"],
                seed=incoming["seed"],
                local_input_path=input_path,
            )
    except Exception as exc:
        if not settings.mock_fallback_enabled:
            raise HTTPException(status_code=502, detail=f"ComfyUI generation failed: {exc}") from exc

        return await _generate_mock(
            image_bytes=incoming["image_bytes"],
            filename=incoming["filename"],
            prompt=incoming["prompt"],
            seed=incoming["seed"],
            local_input_path=input_path,
        )


@app.post("/generate/tryon", response_model=GenerateResponse)
async def generate_tryon(request: Request) -> GenerateResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        incoming = await _parse_tryon_json_request(request)
    elif content_type.startswith("multipart/form-data"):
        incoming = await _parse_tryon_multipart_request(request)
    else:
        raise HTTPException(status_code=415, detail="Use multipart/form-data or application/json")

    if not settings.catvton_script.exists():
        raise HTTPException(status_code=503, detail=f"CatVTON script missing: {settings.catvton_script}")
    if not settings.catvton_root.exists():
        raise HTTPException(status_code=503, detail=f"CatVTON root missing: {settings.catvton_root}")

    cloth_path = _persist_input(incoming["image_bytes"], incoming["filename"])
    person_path = None
    if incoming["person_image_bytes"] is not None:
        person_path = _persist_input(incoming["person_image_bytes"], incoming["person_filename"])

    prepared_cloth_path = settings.upload_dir / f"tryon-prepped-{uuid.uuid4()}.png"
    output_name = f"tryon-{uuid.uuid4()}.png"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.output_dir / output_name

    try:
        async with app.state.gpu_lock:
            prepared_cloth_path = await preprocess_cloth_image(
                comfy=app.state.comfy,
                image_bytes=incoming["image_bytes"],
                filename=incoming["filename"],
                save_to=prepared_cloth_path,
                timeout_seconds=settings.generation_timeout_seconds,
            )
            result = await run_catvton_tryon(
                python_bin=settings.python_bin,
                script_path=settings.catvton_script,
                catvton_root=settings.catvton_root,
                cloth_image=prepared_cloth_path,
                output_path=output_path,
                person_image=person_path,
                person_template=incoming["person_template"],
                cloth_type=incoming["cloth_type"],
                seed=incoming["seed"],
                steps=incoming["steps"],
                guidance=incoming["guidance"],
                width=incoming["width"],
                height=incoming["height"],
                timeout_seconds=settings.tryon_timeout_seconds,
                hf_endpoint=settings.hf_endpoint,
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CatVTON try-on failed: {exc}") from exc

    image_bytes = output_path.read_bytes()
    return GenerateResponse(
        prompt_id=str(uuid.uuid4()),
        pipeline="tryon",
        generator_mode="catvton",
        filename=output_name,
        output_url=_build_output_url(output_name),
        mime_type="image/png",
        image_base64=base64.b64encode(image_bytes).decode("utf-8"),
        comfyui_prompt_id=None,
        local_input_path=str(cloth_path),
        metadata={
            "person_template": incoming["person_template"],
            "person_image_path": str(result.person_path),
            "cloth_type": incoming["cloth_type"],
            "original_cloth_path": str(cloth_path),
            "prepared_cloth_path": str(prepared_cloth_path),
            "seed": incoming["seed"],
            "steps": incoming["steps"],
            "guidance": incoming["guidance"],
            "width": incoming["width"],
            "height": incoming["height"],
        },
    )


@app.post("/generate/edit", response_model=GenerateResponse)
async def generate_edit(request: Request) -> GenerateResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        incoming = await _parse_edit_json_request(request)
    elif content_type.startswith("multipart/form-data"):
        incoming = await _parse_edit_multipart_request(request)
    else:
        raise HTTPException(status_code=415, detail="Use multipart/form-data or application/json")

    input_path = _persist_input(incoming["image_bytes"], incoming["filename"])
    style_reference_paths = _persist_reference_inputs(
        incoming["style_reference_images"],
        prefix="style-reference",
    )
    angle_reference_paths = _persist_reference_inputs(
        incoming["angle_reference_images"],
        prefix="angle-reference",
    )
    source_image = _load_pil_image(incoming["image_bytes"])
    reference_images = [
        *[_load_pil_image(item["image_bytes"]) for item in incoming["style_reference_images"]],
        *[_load_pil_image(item["image_bytes"]) for item in incoming["angle_reference_images"]],
    ]
    final_prompt = _build_reference_aware_prompt(
        incoming["prompt"],
        style_reference_count=len(incoming["style_reference_images"]),
        angle_reference_count=len(incoming["angle_reference_images"]),
    )
    final_negative_prompt = _merge_negative_prompt(incoming["negative_prompt"])

    try:
        async with app.state.gpu_lock:
            result = await run_qwen_edit(
                settings,
                image=source_image,
                reference_images=reference_images,
                prompt=final_prompt,
                negative_prompt=final_negative_prompt,
                seed=incoming["seed"],
                width=incoming["width"],
                height=incoming["height"],
                steps=incoming["steps"],
                true_cfg_scale=incoming["true_cfg_scale"],
                use_lightning=incoming["use_lightning"],
                lightning_lora_scale=incoming["lightning_lora_scale"],
                use_angle_lora=incoming["use_angle_lora"],
                angle_lora_scale=incoming["angle_lora_scale"],
            )
            identity_lock_applied = _should_apply_edit_identity_lock(
                angle_preset=incoming["angle_preset"],
                angle_reference_count=len(incoming["angle_reference_images"]),
            )
            if identity_lock_applied:
                source_cutout = await extract_cutout_rgba(
                    comfy=app.state.comfy,
                    image_bytes=incoming["image_bytes"],
                    filename=incoming["filename"],
                    timeout_seconds=settings.generation_timeout_seconds,
                )
                locked_result = composite_foreground_locked(
                    foreground_rgba=source_cutout,
                    background_rgb=_load_pil_image(result.image_bytes),
                )
                buffer = io.BytesIO()
                locked_result.save(buffer, format="PNG")
                result.image_bytes = buffer.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Qwen edit generation failed: {exc}") from exc

    prompt_id = str(uuid.uuid4())
    output_name = f"qwen-edit-{prompt_id}.png"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.output_dir / output_name
    output_path.write_bytes(result.image_bytes)

    return GenerateResponse(
        prompt_id=prompt_id,
        pipeline="edit",
        generator_mode="qwen-image-edit",
        filename=output_name,
        output_url=_build_output_url(output_name),
        mime_type="image/png",
        image_base64=base64.b64encode(result.image_bytes).decode("utf-8"),
        comfyui_prompt_id=None,
        local_input_path=str(input_path),
        metadata={
            "seed": result.seed,
            "width": result.width,
            "height": result.height,
            "steps": result.steps,
            "true_cfg_scale": result.true_cfg_scale,
            "angle_preset": incoming["angle_preset"],
            "active_adapters": result.active_adapters,
            "adapter_weights": result.adapter_weights,
            "use_lightning": incoming["use_lightning"],
            "use_angle_lora": incoming["use_angle_lora"],
            "negative_prompt": final_negative_prompt,
            "style_reference_count": len(incoming["style_reference_images"]),
            "angle_reference_count": len(incoming["angle_reference_images"]),
            "style_reference_paths": [str(path) for path in style_reference_paths],
            "angle_reference_paths": [str(path) for path in angle_reference_paths],
            "qwen_edit_model_id": settings.qwen_edit_model_id,
            "identity_lock_applied": identity_lock_applied,
        },
    )


@app.post("/generate/reference-scene", response_model=GenerateResponse)
async def generate_reference_scene(request: Request) -> GenerateResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        incoming = await _parse_reference_scene_json_request(request)
    elif content_type.startswith("multipart/form-data"):
        incoming = await _parse_reference_scene_multipart_request(request)
    else:
        raise HTTPException(status_code=415, detail="Use multipart/form-data or application/json")

    input_path = _persist_input(incoming["image_bytes"], incoming["filename"])
    style_reference_paths = _persist_reference_inputs(
        incoming["style_reference_images"],
        prefix="reference-scene-style",
    )

    try:
        async with app.state.gpu_lock:
            source_cutout = await extract_cutout_rgba(
                comfy=app.state.comfy,
                image_bytes=incoming["image_bytes"],
                filename=incoming["filename"],
                timeout_seconds=settings.generation_timeout_seconds,
            )
            neutral_source = build_neutral_product_preview(source_cutout)
            style_reference_images, cleanup_metadata = await prepare_style_reference_images(
                comfy=app.state.comfy,
                references=incoming["style_reference_images"],
                original_paths=style_reference_paths,
                debug_dir=settings.output_dir,
                timeout_seconds=settings.generation_timeout_seconds,
            )
            final_prompt = _build_reference_scene_generation_prompt(
                incoming["prompt"],
                style_reference_count=len(incoming["style_reference_images"]),
                style_reference_cleanup_applied=cleanup_metadata["style_reference_cleanup_applied"],
            )
            final_negative_prompt = _merge_reference_scene_negative_prompt(incoming["negative_prompt"])
            result = await run_qwen_edit(
                settings,
                image=neutral_source,
                reference_images=style_reference_images,
                prompt=final_prompt,
                negative_prompt=final_negative_prompt,
                seed=incoming["seed"],
                width=incoming["width"],
                height=incoming["height"],
                steps=incoming["steps"],
                true_cfg_scale=incoming["true_cfg_scale"],
                use_lightning=False,
                lightning_lora_scale=1.0,
                use_angle_lora=False,
                angle_lora_scale=1.0,
            )
            candidate_image = _load_pil_image(result.image_bytes)
            composite = composite_reference_scene(
                foreground_rgba=source_cutout,
                background_rgb=candidate_image,
                shadow_strength=incoming["shadow_strength"],
                reflection_strength=incoming["reflection_strength"],
                color_harmonize_strength=incoming["color_harmonize_strength"],
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Reference scene generation failed: {exc}") from exc

    prompt_id = str(uuid.uuid4())
    final_name = f"reference-scene-{prompt_id}.png"
    candidate_name = f"reference-scene-candidate-{prompt_id}.png"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = settings.output_dir / candidate_name
    candidate_path.write_bytes(result.image_bytes)
    output_path = settings.output_dir / final_name
    buffer = io.BytesIO()
    composite.image.save(buffer, format="PNG")
    final_image_bytes = buffer.getvalue()
    output_path.write_bytes(final_image_bytes)

    return GenerateResponse(
        prompt_id=prompt_id,
        pipeline="reference_scene",
        generator_mode="qwen-reference-scene",
        filename=final_name,
        output_url=_build_output_url(final_name),
        mime_type="image/png",
        image_base64=base64.b64encode(final_image_bytes).decode("utf-8"),
        comfyui_prompt_id=None,
        local_input_path=str(input_path),
        metadata={
            "seed": result.seed,
            "width": result.width,
            "height": result.height,
            "steps": result.steps,
            "true_cfg_scale": result.true_cfg_scale,
            "negative_prompt": final_negative_prompt,
            "style_reference_count": len(incoming["style_reference_images"]),
            "style_reference_paths": [str(path) for path in style_reference_paths],
            "shadow_strength": incoming["shadow_strength"],
            "reflection_strength": incoming["reflection_strength"],
            "color_harmonize_strength": incoming["color_harmonize_strength"],
            "shadow_applied": composite.shadow_applied,
            "reflection_applied": composite.reflection_applied,
            "foreground_bbox": list(composite.bbox) if composite.bbox else None,
            "identity_lock_applied": True,
            "candidate_filename": candidate_name,
            "candidate_output_url": _build_output_url(candidate_name),
            "qwen_edit_model_id": settings.qwen_edit_model_id,
            **cleanup_metadata,
        },
    )


async def _parse_json_request(request: Request) -> dict:
    payload = GenerateJsonRequest.model_validate(await request.json())
    image_bytes = _decode_base64_image(payload.image_base64, "image_base64")

    return {
        "image_bytes": image_bytes,
        "filename": _safe_filename(payload.filename or "request.png"),
        "prompt": payload.prompt.strip(),
        "negative_prompt": payload.negative_prompt.strip(),
        "seed": payload.seed,
    }


async def _parse_tryon_json_request(request: Request) -> dict:
    payload = TryOnJsonRequest.model_validate(await request.json())
    person_image_bytes = None
    if payload.person_image_base64:
        person_image_bytes = _decode_base64_image(payload.person_image_base64, "person_image_base64")

    return {
        "image_bytes": _decode_base64_image(payload.image_base64, "image_base64"),
        "person_image_bytes": person_image_bytes,
        "filename": _safe_filename(payload.filename or "cloth.png"),
        "person_filename": _safe_filename(payload.person_filename or "person.png"),
        "person_template": payload.person_template,
        "cloth_type": payload.cloth_type,
        "seed": payload.seed,
        "steps": payload.steps,
        "guidance": payload.guidance,
        "width": payload.width,
        "height": payload.height,
    }


async def _parse_edit_json_request(request: Request) -> dict:
    payload = EditJsonRequest.model_validate(await request.json())
    style_reference_images = _decode_reference_images(
        payload.style_reference_images_base64,
        field_name="style_reference_images_base64",
        filename_prefix="style-reference",
    )
    angle_reference_images = _decode_reference_images(
        payload.angle_reference_images_base64,
        field_name="angle_reference_images_base64",
        filename_prefix="angle-reference",
    )
    _validate_reference_image_count(style_reference_images, angle_reference_images)
    prompt, use_angle_lora = _resolve_edit_prompt(payload.prompt, payload.angle_preset, payload.use_angle_lora)
    if not prompt and not style_reference_images and not angle_reference_images:
        raise HTTPException(status_code=400, detail="Missing prompt or angle_preset")

    return {
        "image_bytes": _decode_base64_image(payload.image_base64, "image_base64"),
        "filename": _safe_filename(payload.filename or "edit.png"),
        "prompt": prompt,
        "negative_prompt": payload.negative_prompt.strip(),
        "style_reference_images": style_reference_images,
        "angle_reference_images": angle_reference_images,
        "seed": payload.seed,
        "width": payload.width,
        "height": payload.height,
        "steps": payload.steps,
        "true_cfg_scale": payload.true_cfg_scale,
        "angle_preset": payload.angle_preset,
        "use_angle_lora": use_angle_lora,
        "angle_lora_scale": payload.angle_lora_scale,
        "use_lightning": payload.use_lightning,
        "lightning_lora_scale": payload.lightning_lora_scale,
    }


async def _parse_reference_scene_json_request(request: Request) -> dict:
    payload = ReferenceSceneJsonRequest.model_validate(await request.json())
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")
    style_reference_images = _decode_reference_images(
        payload.style_reference_images_base64,
        field_name="style_reference_images_base64",
        filename_prefix="reference-scene-style",
    )
    _validate_reference_scene_style_images(style_reference_images)
    return {
        "image_bytes": _decode_base64_image(payload.image_base64, "image_base64"),
        "filename": _safe_filename(payload.filename or "reference-scene.png"),
        "prompt": prompt,
        "negative_prompt": payload.negative_prompt.strip(),
        "style_reference_images": style_reference_images,
        "seed": payload.seed,
        "width": payload.width,
        "height": payload.height,
        "steps": payload.steps,
        "true_cfg_scale": payload.true_cfg_scale,
        "shadow_strength": payload.shadow_strength,
        "reflection_strength": payload.reflection_strength,
        "color_harmonize_strength": payload.color_harmonize_strength,
    }


async def _parse_multipart_request(request: Request) -> dict:
    form = await request.form()
    upload = form.get("image")
    prompt = str(form.get("prompt", "")).strip()
    negative_prompt = str(form.get("negative_prompt", "")).strip()
    seed_value = form.get("seed")

    if upload is None or not hasattr(upload, "filename") or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Missing file field: image")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")

    image_bytes = await upload.read()
    seed_text = "" if seed_value is None else str(seed_value).strip()
    seed = int(seed_text) if seed_text else None

    return {
        "image_bytes": image_bytes,
        "filename": _safe_filename(upload.filename or "upload.png"),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
    }


async def _parse_edit_multipart_request(request: Request) -> dict:
    form = await request.form()
    upload = form.get("image")
    style_reference_images = await _read_reference_uploads(
        form,
        singular_field_name="style_reference_image",
        plural_field_name="style_reference_images",
        filename_prefix="style-reference",
    )
    angle_reference_images = await _read_reference_uploads(
        form,
        singular_field_name="angle_reference_image",
        plural_field_name="angle_reference_images",
        filename_prefix="angle-reference",
    )
    _validate_reference_image_count(style_reference_images, angle_reference_images)
    prompt_text = str(form.get("prompt", "")).strip()
    negative_prompt = str(form.get("negative_prompt", "")).strip()
    angle_preset = str(form.get("angle_preset", "")).strip() or None
    use_angle_lora_text = str(form.get("use_angle_lora", "false")).strip()
    use_lightning_text = str(form.get("use_lightning", "false")).strip()
    seed = int(str(form.get("seed", "123")).strip() or "123")
    width_text = str(form.get("width", "")).strip()
    height_text = str(form.get("height", "")).strip()
    steps = int(str(form.get("steps", str(settings.qwen_edit_default_steps))).strip() or str(settings.qwen_edit_default_steps))
    true_cfg_scale = float(
        str(form.get("true_cfg_scale", str(settings.qwen_edit_default_true_cfg_scale))).strip()
        or str(settings.qwen_edit_default_true_cfg_scale)
    )
    angle_lora_scale = float(str(form.get("angle_lora_scale", "1.0")).strip() or "1.0")
    lightning_lora_scale = float(str(form.get("lightning_lora_scale", "1.0")).strip() or "1.0")

    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Missing file field: image")

    prompt, use_angle_lora = _resolve_edit_prompt(
        prompt_text,
        angle_preset,
        _parse_bool_form(use_angle_lora_text, default=False),
    )
    if not prompt and not style_reference_images and not angle_reference_images:
        raise HTTPException(status_code=400, detail="Missing prompt or angle_preset")

    image_bytes = await upload.read()
    return {
        "image_bytes": image_bytes,
        "filename": _safe_filename(upload.filename or "edit.png"),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "style_reference_images": style_reference_images,
        "angle_reference_images": angle_reference_images,
        "seed": seed,
        "width": int(width_text) if width_text else None,
        "height": int(height_text) if height_text else None,
        "steps": steps,
        "true_cfg_scale": true_cfg_scale,
        "angle_preset": angle_preset,
        "use_angle_lora": use_angle_lora,
        "angle_lora_scale": angle_lora_scale,
        "use_lightning": _parse_bool_form(use_lightning_text, default=False),
        "lightning_lora_scale": lightning_lora_scale,
    }


async def _parse_reference_scene_multipart_request(request: Request) -> dict:
    form = await request.form()
    upload = form.get("image")
    style_reference_images = await _read_reference_uploads(
        form,
        singular_field_name="style_reference_image",
        plural_field_name="style_reference_images",
        filename_prefix="reference-scene-style",
    )
    _validate_reference_scene_style_images(style_reference_images)
    prompt = str(form.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Missing file field: image")

    negative_prompt = str(form.get("negative_prompt", "")).strip()
    seed = int(str(form.get("seed", "123")).strip() or "123")
    width_text = str(form.get("width", "")).strip()
    height_text = str(form.get("height", "")).strip()
    steps = int(str(form.get("steps", str(settings.qwen_edit_default_steps))).strip() or str(settings.qwen_edit_default_steps))
    true_cfg_scale = float(
        str(form.get("true_cfg_scale", str(settings.qwen_edit_default_true_cfg_scale))).strip()
        or str(settings.qwen_edit_default_true_cfg_scale)
    )
    shadow_strength = float(str(form.get("shadow_strength", "0.4")).strip() or "0.4")
    reflection_strength = float(str(form.get("reflection_strength", "0.14")).strip() or "0.14")
    color_harmonize_strength = float(str(form.get("color_harmonize_strength", "0.18")).strip() or "0.18")
    image_bytes = await upload.read()
    return {
        "image_bytes": image_bytes,
        "filename": _safe_filename(upload.filename or "reference-scene.png"),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "style_reference_images": style_reference_images,
        "seed": seed,
        "width": int(width_text) if width_text else None,
        "height": int(height_text) if height_text else None,
        "steps": steps,
        "true_cfg_scale": true_cfg_scale,
        "shadow_strength": shadow_strength,
        "reflection_strength": reflection_strength,
        "color_harmonize_strength": color_harmonize_strength,
    }


async def _parse_tryon_multipart_request(request: Request) -> dict:
    form = await request.form()
    cloth_upload = form.get("image")
    person_upload = form.get("person_image")
    person_template = str(form.get("person_template", "woman_1")).strip() or "woman_1"
    cloth_type = str(form.get("cloth_type", "overall")).strip() or "overall"
    seed = int(str(form.get("seed", "42")).strip() or "42")
    steps = int(str(form.get("steps", "30")).strip() or "30")
    guidance = float(str(form.get("guidance", "2.5")).strip() or "2.5")
    width = int(str(form.get("width", "768")).strip() or "768")
    height = int(str(form.get("height", "1024")).strip() or "1024")

    if cloth_upload is None or not hasattr(cloth_upload, "read"):
        raise HTTPException(status_code=400, detail="Missing file field: image")

    image_bytes = await cloth_upload.read()
    person_image_bytes = None
    person_filename = "person.png"
    if person_upload is not None and hasattr(person_upload, "read"):
        person_image_bytes = await person_upload.read()
        person_filename = _safe_filename(person_upload.filename or person_filename)

    return {
        "image_bytes": image_bytes,
        "person_image_bytes": person_image_bytes,
        "filename": _safe_filename(cloth_upload.filename or "cloth.png"),
        "person_filename": person_filename,
        "person_template": person_template,
        "cloth_type": cloth_type,
        "seed": seed,
        "steps": steps,
        "guidance": guidance,
        "width": width,
        "height": height,
    }


async def _generate_with_comfy(
    image_bytes: bytes,
    filename: str,
    prompt: str,
    negative_prompt: str,
    seed: int | None,
    local_input_path: Path,
) -> GenerateResponse:
    comfy_filename = await app.state.comfy.upload_image(image_bytes, filename)
    workflow, bindings = build_workflow(
        settings.workflow_template,
        settings.workflow_bindings,
        image_name=comfy_filename,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
    )
    result = await app.state.comfy.run_workflow(
        workflow,
        preferred_output_nodes=bindings.preferred_output_nodes,
        timeout_seconds=settings.generation_timeout_seconds,
    )

    suffix = Path(result.image_ref.filename).suffix or ".png"
    final_name = f"comfy-{result.prompt_id}{suffix}"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.output_dir / final_name
    output_path.write_bytes(result.image_bytes)
    mime_type = mimetypes.guess_type(final_name)[0] or "image/png"

    return GenerateResponse(
        prompt_id=result.prompt_id,
        pipeline="scene",
        generator_mode="comfyui",
        filename=final_name,
        output_url=_build_output_url(final_name),
        mime_type=mime_type,
        image_base64=base64.b64encode(result.image_bytes).decode("utf-8"),
        comfyui_prompt_id=result.prompt_id,
        local_input_path=str(local_input_path),
        metadata={},
    )


async def _generate_mock(
    image_bytes: bytes,
    filename: str,
    prompt: str,
    seed: int | None,
    local_input_path: Path,
) -> GenerateResponse:
    await asyncio.sleep(settings.mock_delay_seconds)
    prompt_id = str(uuid.uuid4())
    mock_bytes = _render_mock_result(image_bytes, prompt, seed)
    final_name = f"mock-{prompt_id}.png"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.output_dir / final_name
    output_path.write_bytes(mock_bytes)

    return GenerateResponse(
        prompt_id=prompt_id,
        pipeline="scene",
        generator_mode="mock",
        filename=final_name,
        output_url=_build_output_url(final_name),
        mime_type="image/png",
        image_base64=base64.b64encode(mock_bytes).decode("utf-8"),
        comfyui_prompt_id=None,
        local_input_path=str(local_input_path),
        metadata={},
    )


def _persist_input(image_bytes: bytes, filename: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{timestamp}-{filename}"
    path.write_bytes(image_bytes)
    return path


def _resolve_edit_prompt(prompt: str, angle_preset: str | None, requested_use_angle_lora: bool) -> tuple[str, bool]:
    prompt = prompt.strip()
    preset_prompt = ""

    if angle_preset:
        preset = next((item for item in EDIT_PRESETS if item["name"] == angle_preset), None)
        if preset is None:
            raise HTTPException(status_code=400, detail=f"Unknown edit preset: {angle_preset}")
        preset_prompt = str(preset["prompt_template"]).strip()

    full_prompt = "\n".join(part for part in [preset_prompt, prompt] if part).strip()
    return full_prompt, requested_use_angle_lora


def _build_reference_aware_prompt(
    prompt: str,
    *,
    style_reference_count: int,
    angle_reference_count: int,
) -> str:
    instructions = [
        "图片1是商品主图，必须严格保持同一个商品主体。",
        "保持完全相同的颜色、花纹、面料、材质光泽、版型、辅料、logo、比例和结构。",
    ]
    if style_reference_count:
        instructions.append(
            f"附加的 {style_reference_count} 张风格参考图只用于借鉴场景、布光、氛围、配色和构图，"
            "不得复制其中的其他商品、人物或主体。"
        )
    if angle_reference_count:
        instructions.append(
            f"附加的 {angle_reference_count} 张角度参考图只用于借鉴机位、视角、取景和镜头语言，"
            "不得改变商品本体结构和细节。"
        )

    normalized_prompt = prompt.strip() or (
        "基于参考图生成高端电商商品编辑图，只改变场景、光线、氛围或机位，商品主体保持不变。"
    )
    instructions.append(normalized_prompt)
    instructions.append("输出要求：照片级真实，电商广告级美感，边缘干净，细节清晰，材质真实。")
    return "\n".join(instructions)


def _build_reference_scene_generation_prompt(
    prompt: str,
    *,
    style_reference_count: int,
    style_reference_cleanup_applied: bool = False,
) -> str:
    instructions = [
        "图片1是需要保留的商品主体，只允许围绕它生成新的场景和氛围。",
        "保持商品拍摄角度、主体位置、主体尺度和整体构图关系基本一致。",
        "禁止替换商品，禁止改变商品颜色、花纹、面料、材质光泽、版型、长度、辅料、logo 和结构。",
        "输出应当是适合重新合成原商品前景的高质量场景候选图，背景真实，布光合理，空间层次清晰。",
    ]
    if style_reference_count:
        instructions.append(
            f"附加的 {style_reference_count} 张风格参考图只用于借鉴场景空间、布光、色调、氛围、环境反射和镜头情绪，"
            "不得复制其中的人物、商品或主体。"
        )
    if style_reference_cleanup_applied:
        instructions.append("风格参考图中的原主体已被预先清理，请只借鉴剩余环境线索，不要重新生成参考图里的商品或主体。")
    instructions.append(prompt.strip())
    instructions.append("输出要求：高级电商广告质感，环境光真实，画面干净，边缘自然，适合后续商品主体锁定合成。")
    return "\n".join(instructions)


def _should_apply_edit_identity_lock(
    *,
    angle_preset: str | None,
    angle_reference_count: int,
) -> bool:
    if angle_reference_count > 0:
        return False
    if angle_preset and angle_preset not in {"editorial_light_shift"}:
        return False
    return True


def _merge_negative_prompt(negative_prompt: str) -> str:
    normalized = negative_prompt.strip()
    return "\n".join(part for part in [DEFAULT_EDIT_NEGATIVE_PROMPT, normalized] if part)


def _merge_reference_scene_negative_prompt(negative_prompt: str) -> str:
    normalized = negative_prompt.strip()
    return "\n".join(part for part in [DEFAULT_REFERENCE_SCENE_NEGATIVE_PROMPT, normalized] if part)


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "upload.png"


def _strip_data_url_prefix(raw_value: str) -> str:
    if raw_value.startswith("data:"):
        _, _, payload = raw_value.partition(",")
        return payload
    return raw_value


def _decode_base64_image(raw_value: str, field_name: str) -> bytes:
    try:
        return base64.b64decode(_strip_data_url_prefix(raw_value), validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} payload") from exc


def _decode_reference_images(
    raw_values: list[str],
    *,
    field_name: str,
    filename_prefix: str,
) -> list[dict[str, bytes | str]]:
    decoded: list[dict[str, bytes | str]] = []
    for index, raw_value in enumerate(raw_values):
        if not raw_value.strip():
            continue
        decoded.append(
            {
                "image_bytes": _decode_base64_image(raw_value, f"{field_name}[{index}]"),
                "filename": f"{filename_prefix}-{index + 1}.png",
            }
        )
    return decoded


async def _read_reference_uploads(
    form,
    *,
    singular_field_name: str,
    plural_field_name: str,
    filename_prefix: str,
) -> list[dict[str, bytes | str]]:
    uploads: list = []
    for field_name in [singular_field_name, plural_field_name]:
        uploads.extend(item for item in form.getlist(field_name) if hasattr(item, "read"))

    references: list[dict[str, bytes | str]] = []
    for index, upload in enumerate(uploads):
        image_bytes = await upload.read()
        if not image_bytes:
            continue
        references.append(
            {
                "image_bytes": image_bytes,
                "filename": _safe_filename(upload.filename or f"{filename_prefix}-{index + 1}.png"),
            }
        )
    return references


def _validate_reference_image_count(
    style_reference_images: list[dict[str, bytes | str]],
    angle_reference_images: list[dict[str, bytes | str]],
) -> None:
    total = len(style_reference_images) + len(angle_reference_images)
    if total > MAX_EDIT_REFERENCE_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_EDIT_REFERENCE_IMAGES} edit reference images are supported per request",
        )


def _validate_reference_scene_style_images(style_reference_images: list[dict[str, bytes | str]]) -> None:
    if not style_reference_images:
        raise HTTPException(status_code=400, detail="At least one style reference image is required")
    if len(style_reference_images) > MAX_REFERENCE_SCENE_STYLE_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_REFERENCE_SCENE_STYLE_IMAGES} style reference images are supported per request",
        )


def _persist_reference_inputs(
    references: list[dict[str, bytes | str]],
    *,
    prefix: str,
) -> list[Path]:
    paths: list[Path] = []
    for index, item in enumerate(references):
        paths.append(_persist_input(item["image_bytes"], f"{prefix}-{index + 1}-{item['filename']}"))
    return paths


def _load_pil_image(image_bytes: bytes) -> Image.Image:
    with Image.open(io.BytesIO(image_bytes)) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def _is_hf_repo_cached(cache_dir: Path, repo_id: str) -> bool:
    ready, _ = _inspect_hf_repo_cache(cache_dir, repo_id)
    return ready


def _inspect_hf_repo_cache(cache_dir: Path, repo_id: str) -> tuple[bool, list[str]]:
    repo_cache_dir = cache_dir / f"models--{repo_id.replace('/', '--')}"
    snapshots_dir = repo_cache_dir / "snapshots"
    issues: list[str] = []

    if not snapshots_dir.exists():
        return False, ["missing snapshots directory"]

    snapshots = sorted(path for path in snapshots_dir.iterdir() if path.is_dir())
    if not snapshots:
        return False, ["no snapshot directories found"]

    snapshot_dir = max(snapshots, key=lambda path: path.stat().st_mtime)
    model_index_path = snapshot_dir / "model_index.json"
    if not model_index_path.exists():
        issues.append("missing model_index.json")

    required_components = ["processor", "scheduler", "text_encoder", "tokenizer", "transformer", "vae"]
    if model_index_path.exists():
        try:
            model_index = json.loads(model_index_path.read_text())
            required_components = [
                key
                for key, value in model_index.items()
                if not key.startswith("_") and isinstance(value, list) and len(value) == 2
            ]
        except Exception as exc:
            issues.append(f"invalid model_index.json: {exc}")

    for component in required_components:
        component_dir = snapshot_dir / component
        if not component_dir.exists():
            issues.append(f"missing component directory: {component}")
            continue
        if not any(component_dir.iterdir()):
            issues.append(f"empty component directory: {component}")

    incomplete_blobs = sorted(repo_cache_dir.glob("blobs/*.incomplete"))
    if incomplete_blobs:
        issues.append(f"incomplete blobs remaining: {len(incomplete_blobs)}")

    broken_links: list[str] = []
    for path in snapshot_dir.rglob("*"):
        if path.is_symlink() and not path.exists():
            broken_links.append(str(path.relative_to(snapshot_dir)))
            if len(broken_links) >= 5:
                break
    if broken_links:
        issues.append(f"broken snapshot links: {', '.join(broken_links)}")

    return len(issues) == 0, issues


def _parse_bool_form(raw_value: str, *, default: bool) -> bool:
    value = raw_value.strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise HTTPException(status_code=400, detail=f"Invalid boolean value: {raw_value}")


def _render_mock_result(image_bytes: bytes, prompt: str, seed: int | None) -> bytes:
    product = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    canvas = Image.new("RGBA", (1400, 960), (244, 238, 226, 255))

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((440, 620, 980, 800), fill=(84, 66, 44, 64))
    shadow = shadow.filter(ImageFilter.GaussianBlur(32))
    canvas.alpha_composite(shadow)

    product.thumbnail((640, 640))
    x = (canvas.width - product.width) // 2
    y = 170
    canvas.alpha_composite(product, (x, y))

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.rounded_rectangle((90, 64, 1310, 146), radius=24, fill=(255, 252, 247, 220))
    draw.text((120, 92), "MOCK PIPELINE OUTPUT", fill=(98, 66, 33), font=font)

    prompt_block = Image.new("RGBA", (1120, 160), (255, 255, 255, 210))
    prompt_draw = ImageDraw.Draw(prompt_block)
    prompt_draw.rounded_rectangle((0, 0, 1120, 160), radius=24, fill=(255, 255, 255, 214))
    prompt_draw.text((36, 26), f"Prompt: {prompt[:180]}", fill=(32, 27, 22), font=font)
    if seed is not None:
        prompt_draw.text((36, 92), f"Seed: {seed}", fill=(96, 86, 74), font=font)
    canvas.alpha_composite(prompt_block, (140, 742))

    buffer = io.BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


from PIL import ImageFilter  # noqa: E402
