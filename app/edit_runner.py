from __future__ import annotations

import asyncio
import io
import math
import os
import threading
from dataclasses import dataclass

import torch
from diffusers import FlowMatchEulerDiscreteScheduler, QwenImageEditPlusPipeline
from PIL import Image, ImageOps

from app.config import Settings


LIGHTNING_SCHEDULER_CONFIG = {
    "base_image_seq_len": 256,
    "base_shift": math.log(3),
    "invert_sigmas": False,
    "max_image_seq_len": 8192,
    "max_shift": math.log(3),
    "num_train_timesteps": 1000,
    "shift": 1.0,
    "shift_terminal": None,
    "stochastic_sampling": False,
    "time_shift_type": "exponential",
    "use_beta_sigmas": False,
    "use_dynamic_shifting": True,
    "use_exponential_sigmas": False,
    "use_karras_sigmas": False,
}


@dataclass(slots=True)
class QwenEditRunResult:
    image_bytes: bytes
    seed: int
    width: int
    height: int
    steps: int
    true_cfg_scale: float
    active_adapters: list[str]
    adapter_weights: list[float]


class QwenEditService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pipeline: QwenImageEditPlusPipeline | None = None
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._loaded_adapters: set[str] = set()

    def _configure_hf_env(self) -> None:
        cache_dir = str(self.settings.qwen_edit_cache_dir)
        os.environ.setdefault("HF_ENDPOINT", self.settings.hf_endpoint)
        os.environ.setdefault("HF_HOME", cache_dir)
        os.environ.setdefault("HF_HUB_CACHE", cache_dir)
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    def _load_pipeline(self) -> QwenImageEditPlusPipeline:
        self._configure_hf_env()
        pipeline = QwenImageEditPlusPipeline.from_pretrained(
            self.settings.qwen_edit_model_id,
            torch_dtype=torch.bfloat16,
            cache_dir=str(self.settings.qwen_edit_cache_dir),
        )
        pipeline.set_progress_bar_config(disable=True)
        if hasattr(pipeline, "vae") and pipeline.vae is not None:
            pipeline.vae.enable_slicing()
            pipeline.vae.enable_tiling()

        if self.settings.qwen_edit_enable_lightning:
            pipeline.load_lora_weights(
                self.settings.qwen_edit_lightning_repo,
                weight_name=self.settings.qwen_edit_lightning_filename,
                adapter_name="lightning",
                cache_dir=str(self.settings.qwen_edit_cache_dir),
            )
            pipeline.scheduler = FlowMatchEulerDiscreteScheduler.from_config(LIGHTNING_SCHEDULER_CONFIG)
            self._loaded_adapters.add("lightning")

        if self.settings.qwen_edit_enable_angle_lora:
            pipeline.load_lora_weights(
                self.settings.qwen_edit_angle_lora_repo,
                weight_name=self.settings.qwen_edit_angle_lora_filename,
                adapter_name="multiple_angles",
                cache_dir=str(self.settings.qwen_edit_cache_dir),
            )
            self._loaded_adapters.add("multiple_angles")

        if self.settings.qwen_edit_cpu_offload:
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to("cuda")

        return pipeline

    def _ensure_pipeline(self) -> QwenImageEditPlusPipeline:
        if self._pipeline is not None:
            return self._pipeline

        with self._load_lock:
            if self._pipeline is None:
                self._pipeline = self._load_pipeline()
        return self._pipeline

    @staticmethod
    def _round_dim(value: int) -> int:
        return max(512, int(round(value / 32.0) * 32))

    def _resolve_size(self, image: Image.Image, width: int | None, height: int | None) -> tuple[int, int]:
        if width and height:
            return self._round_dim(width), self._round_dim(height)

        src_w, src_h = image.size
        max_side = self.settings.qwen_edit_default_max_side
        if src_w >= src_h:
            scale = max_side / max(src_w, 1)
        else:
            scale = max_side / max(src_h, 1)

        target_w = width or int(src_w * scale)
        target_h = height or int(src_h * scale)
        return self._round_dim(target_w), self._round_dim(target_h)

    def _apply_adapters(
        self,
        pipeline: QwenImageEditPlusPipeline,
        *,
        use_lightning: bool,
        lightning_lora_scale: float,
        use_angle_lora: bool,
        angle_lora_scale: float,
    ) -> tuple[list[str], list[float]]:
        adapter_names: list[str] = []
        adapter_weights: list[float] = []

        if use_lightning:
            if "lightning" not in self._loaded_adapters:
                raise RuntimeError("Lightning LoRA is not loaded. Check qwen edit settings.")
            adapter_names.append("lightning")
            adapter_weights.append(float(lightning_lora_scale))

        if use_angle_lora:
            if "multiple_angles" not in self._loaded_adapters:
                raise RuntimeError("Multiple-angles LoRA is not loaded. Check qwen edit settings.")
            adapter_names.append("multiple_angles")
            adapter_weights.append(float(angle_lora_scale))

        if not adapter_names:
            raise RuntimeError("No active Qwen Edit adapters selected.")

        pipeline.set_adapters(adapter_names, adapter_weights)
        return adapter_names, adapter_weights

    def generate(
        self,
        *,
        image: Image.Image,
        prompt: str,
        negative_prompt: str,
        seed: int,
        width: int | None,
        height: int | None,
        steps: int,
        true_cfg_scale: float,
        use_lightning: bool,
        lightning_lora_scale: float,
        use_angle_lora: bool,
        angle_lora_scale: float,
    ) -> QwenEditRunResult:
        pipeline = self._ensure_pipeline()
        source = ImageOps.exif_transpose(image).convert("RGB")
        final_width, final_height = self._resolve_size(source, width, height)

        with self._run_lock:
            active_adapters, adapter_weights = self._apply_adapters(
                pipeline,
                use_lightning=use_lightning,
                lightning_lora_scale=lightning_lora_scale,
                use_angle_lora=use_angle_lora,
                angle_lora_scale=angle_lora_scale,
            )
            generator = torch.Generator(device="cpu").manual_seed(seed)
            with torch.inference_mode():
                output = pipeline(
                    image=source,
                    prompt=prompt,
                    negative_prompt=negative_prompt or None,
                    true_cfg_scale=true_cfg_scale,
                    width=final_width,
                    height=final_height,
                    num_inference_steps=steps,
                    generator=generator,
                )
            result_image = output.images[0].convert("RGB")

        buffer = io.BytesIO()
        result_image.save(buffer, format="PNG")
        return QwenEditRunResult(
            image_bytes=buffer.getvalue(),
            seed=seed,
            width=final_width,
            height=final_height,
            steps=steps,
            true_cfg_scale=true_cfg_scale,
            active_adapters=active_adapters,
            adapter_weights=adapter_weights,
        )


_SERVICE_LOCK = threading.Lock()
_SERVICE: QwenEditService | None = None


def get_qwen_edit_service(settings: Settings) -> QwenEditService:
    global _SERVICE
    if _SERVICE is not None:
        return _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = QwenEditService(settings)
    return _SERVICE


async def run_qwen_edit(
    settings: Settings,
    *,
    image: Image.Image,
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int | None,
    height: int | None,
    steps: int,
    true_cfg_scale: float,
    use_lightning: bool,
    lightning_lora_scale: float,
    use_angle_lora: bool,
    angle_lora_scale: float,
) -> QwenEditRunResult:
    service = get_qwen_edit_service(settings)
    return await asyncio.to_thread(
        service.generate,
        image=image,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        width=width,
        height=height,
        steps=steps,
        true_cfg_scale=true_cfg_scale,
        use_lightning=use_lightning,
        lightning_lora_scale=lightning_lora_scale,
        use_angle_lora=use_angle_lora,
        angle_lora_scale=angle_lora_scale,
    )
