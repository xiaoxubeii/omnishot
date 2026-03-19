from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import subprocess
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

import httpx
from mcp.server.fastmcp import FastMCP

from app.config import ROOT_DIR, get_settings


settings = get_settings()


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


class OmnishotAPI:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_json(self, path: str) -> dict | list[dict]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

    async def post_multipart(
        self,
        path: str,
        *,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout_seconds) as client:
            response = await client.post(path, files=files, data=data)
            return _parse_http_response(response)


def _is_http_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _strip_data_url_prefix(value: str) -> str:
    if value.startswith("data:"):
        _, _, payload = value.partition(",")
        return payload
    return value


def _decode_base64_payload(value: str, field_name: str) -> bytes:
    try:
        return base64.b64decode(_strip_data_url_prefix(value), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid base64 payload for {field_name}") from exc


def _guess_filename_from_url(url: str, fallback: str) -> str:
    path = Path(urlsplit(url).path)
    return path.name or fallback


async def _load_binary_source(
    *,
    path_value: str | None = None,
    url_value: str | None = None,
    base64_value: str | None = None,
    filename: str | None = None,
    default_filename: str,
    timeout_seconds: float,
) -> tuple[str, bytes, str]:
    normalized_path = path_value.strip() if path_value else ""
    normalized_url = url_value.strip() if url_value else ""
    normalized_base64 = base64_value.strip() if base64_value else ""
    if normalized_path and _is_http_url(normalized_path) and not normalized_url:
        normalized_url = normalized_path
        normalized_path = ""

    provided = [
        ("path", normalized_path),
        ("url", normalized_url),
        ("base64", normalized_base64),
    ]
    active = [(kind, value) for kind, value in provided if value]
    if not active:
        raise ValueError("One of image_path/image_url/image_base64 must be provided.")
    if len(active) > 1:
        kinds = ", ".join(kind for kind, _ in active)
        raise ValueError(f"Provide exactly one image source, got: {kinds}")

    source_kind, source_value = active[0]
    resolved_filename = (filename or default_filename).strip() or default_filename

    if source_kind == "path":
        file_path = _resolve_path(source_value)
        if not file_path.is_file():
            raise ValueError(f"Image file not found: {file_path}")
        return (
            file_path.name,
            file_path.read_bytes(),
            mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
        )

    if source_kind == "url":
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(source_value)
            response.raise_for_status()
        guessed_name = filename or _guess_filename_from_url(source_value, default_filename)
        mime_type = response.headers.get("content-type", "").split(";", 1)[0].strip() or (
            mimetypes.guess_type(guessed_name)[0] or "application/octet-stream"
        )
        return (guessed_name, response.content, mime_type)

    image_bytes = _decode_base64_payload(source_value, "image_base64")
    return (
        resolved_filename,
        image_bytes,
        mimetypes.guess_type(resolved_filename)[0] or "application/octet-stream",
    )


def _parse_http_response(response: httpx.Response) -> dict[str, Any]:
    text = response.text
    try:
        payload = response.json()
    except Exception:
        if response.is_error:
            raise RuntimeError(f"{response.status_code} {response.reason_phrase}: {text}".strip())
        raise RuntimeError(f"Expected JSON response but got: {text[:500]}")

    if response.is_error:
        detail = payload.get("detail", payload)
        raise RuntimeError(f"{response.status_code} {detail}")
    return payload


def _resolve_output_url(api_base_url: str, output_url: str | None) -> str | None:
    if not output_url:
        return None
    if _is_http_url(output_url):
        return output_url
    return urljoin(f"{api_base_url.rstrip('/')}/", output_url.lstrip("/"))


def _materialize_local_output(payload: dict[str, Any]) -> str | None:
    filename = str(payload.get("filename") or "").strip()
    if not filename:
        return None
    target = settings.output_dir / filename
    image_base64 = payload.get("image_base64")
    if image_base64:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_decode_base64_payload(str(image_base64), "image_base64"))
        return str(target)
    return str(target) if target.exists() else None


def _compact_generation_payload(
    payload: dict[str, Any],
    *,
    include_image_base64: bool,
    api_base_url: str,
) -> dict[str, Any]:
    resolved_output_url = _resolve_output_url(api_base_url, payload.get("output_url"))
    result = {
        "prompt_id": payload.get("prompt_id"),
        "pipeline": payload.get("pipeline"),
        "generator_mode": payload.get("generator_mode"),
        "filename": payload.get("filename"),
        "output_url": payload.get("output_url"),
        "resolved_output_url": resolved_output_url,
        "output_path": _materialize_local_output(payload),
        "mime_type": payload.get("mime_type"),
        "local_input_path": payload.get("local_input_path"),
        "metadata": payload.get("metadata", {}),
    }
    if include_image_base64:
        result["image_base64"] = payload.get("image_base64")
    return result


def _build_server(
    *,
    api_base_url: str,
    host: str,
    port: int,
    mount_path: str,
    streamable_http_path: str,
) -> FastMCP:
    api = OmnishotAPI(api_base_url)
    server = FastMCP(
        name="omnishot",
        instructions=(
            "Use these tools to interact with the Omnishot ecommerce image pipeline. "
            "Scene tools preserve the original product while changing scene and lighting. "
            "Try-on tools render model-wearing images through CatVTON. "
            "Edit tools use Qwen-Image-Edit-2509 plus multiple-angle LoRA for online editing and viewpoint changes. "
            "The FastAPI backend and ComfyUI services should be running before generation. "
            "For remote deployments, prefer image_url or image_base64 when the caller does not share the same filesystem."
        ),
        host=host,
        port=port,
        mount_path=mount_path,
        streamable_http_path=streamable_http_path,
        json_response=True,
        dependencies=["httpx", "mcp", "fastapi", "pillow", "diffusers", "transformers", "accelerate"],
    )

    @server.resource(
        "omnishot://readme",
        name="readme",
        title="Project README",
        description="Project overview and local usage instructions.",
        mime_type="text/markdown",
    )
    def readme_resource() -> str:
        return (ROOT_DIR / "README.md").read_text(encoding="utf-8")

    @server.resource(
        "omnishot://health",
        name="health_resource",
        title="Backend Health",
        description="Current health status for the Omnishot API and ComfyUI bridge.",
        mime_type="application/json",
    )
    async def health_resource() -> str:
        payload = await api.get_json("/api/health")
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @server.resource(
        "omnishot://scene-presets",
        name="scene_presets_resource",
        title="Scene Presets",
        description="Built-in scene generation presets.",
        mime_type="application/json",
    )
    async def scene_presets_resource() -> str:
        payload = await api.get_json("/api/presets/scenes")
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @server.resource(
        "omnishot://tryon-templates",
        name="tryon_templates_resource",
        title="Try-On Templates",
        description="Available built-in try-on person templates.",
        mime_type="application/json",
    )
    async def tryon_templates_resource() -> str:
        payload = await api.get_json("/api/presets/tryon-templates")
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @server.resource(
        "omnishot://edit-presets",
        name="edit_presets_resource",
        title="Edit Presets",
        description="Built-in Qwen edit presets for camera angle and online product editing.",
        mime_type="application/json",
    )
    async def edit_presets_resource() -> str:
        payload = await api.get_json("/api/presets/edit-presets")
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @server.tool(
        name="health",
        description="Return Omnishot backend health, including ComfyUI reachability and workflow status.",
        structured_output=True,
    )
    async def health_tool() -> dict[str, Any]:
        payload = await api.get_json("/api/health")
        return dict(payload)

    @server.tool(
        name="list_scene_presets",
        description="List built-in scene presets available for scene generation.",
        structured_output=True,
    )
    async def list_scene_presets() -> list[dict[str, Any]]:
        payload = await api.get_json("/api/presets/scenes")
        return list(payload)

    @server.tool(
        name="list_tryon_templates",
        description="List built-in model templates available for try-on generation.",
        structured_output=True,
    )
    async def list_tryon_templates() -> list[dict[str, Any]]:
        payload = await api.get_json("/api/presets/tryon-templates")
        return list(payload)

    @server.tool(
        name="list_edit_presets",
        description="List built-in Qwen edit presets for camera angle changes and online editing.",
        structured_output=True,
    )
    async def list_edit_presets() -> list[dict[str, Any]]:
        payload = await api.get_json("/api/presets/edit-presets")
        return list(payload)

    @server.tool(
        name="generate_scene",
        description=(
            "Generate a product scene image from a local image path, remote image URL, or base64 payload. "
            "This changes scene and lighting while keeping the original product identity."
        ),
        structured_output=True,
    )
    async def generate_scene(
        prompt: str,
        image_path: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
        filename: str | None = None,
        negative_prompt: str = "",
        seed: int | None = None,
        include_image_base64: bool = False,
        timeout_seconds: float = 1800.0,
    ) -> dict[str, Any]:
        resolved_filename, image_bytes, mime_type = await _load_binary_source(
            path_value=image_path,
            url_value=image_url,
            base64_value=image_base64,
            filename=filename,
            default_filename="scene.png",
            timeout_seconds=min(timeout_seconds, 120.0),
        )
        data = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
        }
        if seed is not None:
            data["seed"] = str(seed)

        payload = await api.post_multipart(
            "/generate/scene",
            files={"image": (resolved_filename, image_bytes, mime_type)},
            data=data,
            timeout_seconds=timeout_seconds,
        )
        return _compact_generation_payload(
            payload,
            include_image_base64=include_image_base64,
            api_base_url=api_base_url,
        )

    @server.tool(
        name="generate_tryon",
        description=(
            "Generate a model try-on image from a cloth image path, remote image URL, or base64 payload, "
            "with either a built-in template or a custom person image."
        ),
        structured_output=True,
    )
    async def generate_tryon(
        cloth_image_path: str | None = None,
        cloth_image_url: str | None = None,
        cloth_image_base64: str | None = None,
        cloth_filename: str | None = None,
        person_template: str = "woman_1",
        person_image_path: str | None = None,
        person_image_url: str | None = None,
        person_image_base64: str | None = None,
        person_filename: str | None = None,
        cloth_type: Literal["upper", "lower", "overall"] = "overall",
        steps: int = 30,
        guidance: float = 2.5,
        seed: int = 123,
        include_image_base64: bool = False,
        timeout_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        cloth_name, cloth_bytes, cloth_mime = await _load_binary_source(
            path_value=cloth_image_path,
            url_value=cloth_image_url,
            base64_value=cloth_image_base64,
            filename=cloth_filename,
            default_filename="cloth.png",
            timeout_seconds=min(timeout_seconds, 120.0),
        )
        files: dict[str, tuple[str, bytes, str]] = {
            "image": (
                cloth_name,
                cloth_bytes,
                cloth_mime,
            )
        }
        if person_image_path or person_image_url or person_image_base64:
            person_name, person_bytes, person_mime = await _load_binary_source(
                path_value=person_image_path,
                url_value=person_image_url,
                base64_value=person_image_base64,
                filename=person_filename,
                default_filename="person.png",
                timeout_seconds=min(timeout_seconds, 120.0),
            )
            files["person_image"] = (
                person_name,
                person_bytes,
                person_mime,
            )

        data = {
            "person_template": person_template,
            "cloth_type": cloth_type,
            "steps": str(steps),
            "guidance": str(guidance),
            "seed": str(seed),
        }
        payload = await api.post_multipart(
            "/generate/tryon",
            files=files,
            data=data,
            timeout_seconds=timeout_seconds,
        )
        return _compact_generation_payload(
            payload,
            include_image_base64=include_image_base64,
            api_base_url=api_base_url,
        )

    @server.tool(
        name="generate_edit",
        description=(
            "Generate a Qwen-based edited product image from a local image path, remote image URL, or base64 payload. "
            "Supports camera-angle presets and prompt-based online image editing."
        ),
        structured_output=True,
    )
    async def generate_edit(
        image_path: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
        filename: str | None = None,
        prompt: str = "",
        angle_preset: str | None = None,
        negative_prompt: str = "",
        use_angle_lora: bool = True,
        angle_lora_scale: float = 1.0,
        use_lightning: bool = True,
        lightning_lora_scale: float = 1.0,
        steps: int = 8,
        true_cfg_scale: float = 1.0,
        seed: int = 123,
        width: int | None = None,
        height: int | None = None,
        include_image_base64: bool = False,
        timeout_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        resolved_filename, image_bytes, mime_type = await _load_binary_source(
            path_value=image_path,
            url_value=image_url,
            base64_value=image_base64,
            filename=filename,
            default_filename="edit.png",
            timeout_seconds=min(timeout_seconds, 120.0),
        )
        data = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "angle_preset": angle_preset or "",
            "use_angle_lora": str(use_angle_lora).lower(),
            "angle_lora_scale": str(angle_lora_scale),
            "use_lightning": str(use_lightning).lower(),
            "lightning_lora_scale": str(lightning_lora_scale),
            "steps": str(steps),
            "true_cfg_scale": str(true_cfg_scale),
            "seed": str(seed),
        }
        if width is not None:
            data["width"] = str(width)
        if height is not None:
            data["height"] = str(height)

        payload = await api.post_multipart(
            "/generate/edit",
            files={
                "image": (
                    resolved_filename,
                    image_bytes,
                    mime_type,
                )
            },
            data=data,
            timeout_seconds=timeout_seconds,
        )
        return _compact_generation_payload(
            payload,
            include_image_base64=include_image_base64,
            api_base_url=api_base_url,
        )

    @server.tool(
        name="run_catalog_batch_once",
        description=(
            "Run one batch generation pass over an input directory using the existing catalog_generate.py script. "
            "Generates both scene and try-on outputs and writes a manifest."
        ),
        structured_output=True,
    )
    def run_catalog_batch_once(
        input_dir: str,
        output_dir: str,
        product_brief: str = "高端电商服饰商品主图",
        scene_count: int = 4,
        tryon_templates: list[str] | None = None,
        cloth_type: Literal["upper", "lower", "overall"] = "overall",
        timeout_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        resolved_input = _resolve_path(input_dir)
        resolved_output = _resolve_path(output_dir)
        if not resolved_input.is_dir():
            raise ValueError(f"Input directory not found: {resolved_input}")

        templates = tryon_templates or ["woman_1", "woman_2", "woman_3"]
        cmd = [
            str(settings.python_bin),
            str(ROOT_DIR / "scripts/catalog_generate.py"),
            "--once",
            "--api-base-url",
            api_base_url,
            "--input-dir",
            str(resolved_input),
            "--output-dir",
            str(resolved_output),
            "--product-brief",
            product_brief,
            "--scene-count",
            str(scene_count),
            "--tryon-templates",
            ",".join(templates),
            "--cloth-type",
            cloth_type,
            "--timeout",
            str(timeout_seconds),
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"catalog_generate failed with exit code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return {
            "status": "ok",
            "input_dir": str(resolved_input),
            "output_dir": str(resolved_output),
            "manifest_path": str(resolved_output / "manifest.jsonl"),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    @server.tool(
        name="run_batch_generate_once",
        description=(
            "Run one batch generation pass using batch_generate.py. "
            "Supports scene jobs, Qwen edit jobs, or both."
        ),
        structured_output=True,
    )
    def run_batch_generate_once(
        input_dir: str,
        output_dir: str,
        job_type: Literal["scene", "edit", "both"] = "scene",
        scenes_file: str | None = None,
        edits_file: str | None = None,
        timeout_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        resolved_input = _resolve_path(input_dir)
        resolved_output = _resolve_path(output_dir)
        if not resolved_input.is_dir():
            raise ValueError(f"Input directory not found: {resolved_input}")

        cmd = [
            str(settings.python_bin),
            str(ROOT_DIR / "scripts/batch_generate.py"),
            "--once",
            "--api-url",
            f"{api_base_url.rstrip('/')}/generate/scene",
            "--edit-api-url",
            f"{api_base_url.rstrip('/')}/generate/edit",
            "--input-dir",
            str(resolved_input),
            "--output-dir",
            str(resolved_output),
            "--job-type",
            job_type,
            "--request-timeout",
            str(timeout_seconds),
        ]
        if scenes_file:
            cmd.extend(["--scenes-file", str(_resolve_path(scenes_file))])
        if edits_file:
            cmd.extend(["--edits-file", str(_resolve_path(edits_file))])

        completed = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"batch_generate failed with exit code {completed.returncode}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return {
            "status": "ok",
            "job_type": job_type,
            "input_dir": str(resolved_input),
            "output_dir": str(resolved_output),
            "manifest_path": str(resolved_output / "manifest.jsonl"),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Omnishot MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.environ.get("OMNISHOT_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("OMNISHOT_API_BASE_URL", f"http://127.0.0.1:{settings.port}"),
    )
    parser.add_argument("--host", default=os.environ.get("OMNISHOT_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OMNISHOT_MCP_PORT", "8765")))
    parser.add_argument("--mount-path", default=os.environ.get("OMNISHOT_MCP_MOUNT_PATH", "/"))
    parser.add_argument("--streamable-http-path", default=os.environ.get("OMNISHOT_MCP_PATH", "/mcp"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = _build_server(
        api_base_url=args.api_base_url,
        host=args.host,
        port=args.port,
        mount_path=args.mount_path,
        streamable_http_path=args.streamable_http_path,
    )
    server.run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
