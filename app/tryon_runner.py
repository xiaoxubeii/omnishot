import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from app.tryon_templates import TRYON_TEMPLATE_IMAGES


@dataclass(slots=True)
class TryOnRunResult:
    output_path: Path
    person_path: Path
    stdout: str
    stderr: str


async def run_catvton_tryon(
    *,
    python_bin: Path,
    script_path: Path,
    catvton_root: Path,
    cloth_image: Path,
    output_path: Path,
    person_image: Path | None,
    person_template: str,
    cloth_type: str,
    seed: int,
    steps: int,
    guidance: float,
    width: int,
    height: int,
    timeout_seconds: int,
    hf_endpoint: str,
) -> TryOnRunResult:
    if person_image is None:
        try:
            person_path = TRYON_TEMPLATE_IMAGES[person_template]
        except KeyError as exc:
            raise ValueError(f"Unknown try-on template: {person_template}") from exc
    else:
        person_path = person_image

    cmd = [
        str(python_bin),
        str(script_path),
        "--cloth-image",
        str(cloth_image),
        "--output",
        str(output_path),
        "--cloth-type",
        cloth_type,
        "--seed",
        str(seed),
        "--steps",
        str(steps),
        "--guidance",
        str(guidance),
        "--width",
        str(width),
        "--height",
        str(height),
        "--catvton-root",
        str(catvton_root),
    ]
    if person_image is None:
        cmd.extend(["--person-template", person_template])
    else:
        cmd.extend(["--person-image", str(person_image)])

    env = os.environ.copy()
    env.setdefault("HF_ENDPOINT", hf_endpoint)
    env.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(script_path.parent.parent),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if process.returncode != 0:
        raise RuntimeError(
            f"CatVTON failed with exit code {process.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
    if not output_path.exists():
        raise RuntimeError(f"CatVTON finished without creating output: {output_path}")

    return TryOnRunResult(
        output_path=output_path,
        person_path=person_path,
        stdout=stdout,
        stderr=stderr,
    )
