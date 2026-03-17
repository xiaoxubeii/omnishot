import asyncio
import json
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import websockets


@dataclass(slots=True)
class ComfyImageRef:
    filename: str
    subfolder: str = ""
    type: str = "output"


@dataclass(slots=True)
class ComfyRunResult:
    prompt_id: str
    image_ref: ComfyImageRef
    image_bytes: bytes
    history_entry: dict


class ComfyClient:
    def __init__(self, base_url: str, ws_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url.rstrip("/")
        self.http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def health(self) -> dict:
        response = await self.http.get("/queue")
        response.raise_for_status()
        return response.json()

    async def upload_image(self, image_bytes: bytes, filename: str) -> str:
        response = await self.http.post(
            "/upload/image",
            data={"type": "input", "overwrite": "true"},
            files={"image": (filename, image_bytes, "application/octet-stream")},
        )
        response.raise_for_status()
        payload = response.json()

        relative_name = payload["name"]
        if payload.get("subfolder"):
            relative_name = f"{payload['subfolder']}/{payload['name']}"

        if payload.get("type") == "input" and not payload.get("subfolder"):
            return relative_name
        return f"{relative_name} [{payload.get('type', 'input')}]"

    async def queue_prompt(self, prompt: dict, client_id: str, prompt_id: str) -> None:
        response = await self.http.post(
            "/prompt",
            json={
                "prompt": prompt,
                "client_id": client_id,
                "prompt_id": prompt_id,
            },
        )
        response.raise_for_status()

    async def get_history_entry(self, prompt_id: str) -> dict | None:
        response = await self.http.get(f"/history/{prompt_id}")
        response.raise_for_status()
        payload = response.json()
        return payload.get(prompt_id)

    async def download_image(self, image_ref: ComfyImageRef) -> bytes:
        query = urlencode(
            {
                "filename": image_ref.filename,
                "subfolder": image_ref.subfolder,
                "type": image_ref.type,
            }
        )
        response = await self.http.get(f"/view?{query}")
        response.raise_for_status()
        return response.content

    async def run_workflow(
        self,
        prompt: dict,
        preferred_output_nodes: list[str],
        timeout_seconds: int,
    ) -> ComfyRunResult:
        client_id = str(uuid.uuid4())
        prompt_id = str(uuid.uuid4())
        submitted = False

        try:
            async with websockets.connect(
                f"{self.ws_url}?clientId={client_id}",
                open_timeout=10,
                max_size=None,
            ) as websocket:
                await self.queue_prompt(prompt, client_id, prompt_id)
                submitted = True
                await self._wait_for_websocket_completion(websocket, prompt_id, timeout_seconds)
        except Exception:
            if not submitted:
                await self.queue_prompt(prompt, client_id, prompt_id)
            await self._poll_history_until_complete(prompt_id, timeout_seconds)

        history_entry = await self.get_history_entry(prompt_id)
        if history_entry is None:
            raise RuntimeError(f"ComfyUI did not return history for prompt {prompt_id}")

        image_ref = self._select_image(history_entry, preferred_output_nodes)
        image_bytes = await self.download_image(image_ref)

        return ComfyRunResult(
            prompt_id=prompt_id,
            image_ref=image_ref,
            image_bytes=image_bytes,
            history_entry=history_entry,
        )

    async def _wait_for_websocket_completion(
        self,
        websocket,
        prompt_id: str,
        timeout_seconds: int,
    ) -> None:
        while True:
            raw_message = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
            if isinstance(raw_message, bytes):
                continue

            message = json.loads(raw_message)
            message_type = message.get("type")
            data = message.get("data", {})

            if message_type == "execution_error" and data.get("prompt_id") == prompt_id:
                raise RuntimeError(data.get("exception_message", "Unknown ComfyUI execution error"))

            if (
                message_type == "executing"
                and data.get("prompt_id") == prompt_id
                and data.get("node") is None
            ):
                return

    async def _poll_history_until_complete(self, prompt_id: str, timeout_seconds: int) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            history_entry = await self.get_history_entry(prompt_id)
            if history_entry is not None:
                return
            await asyncio.sleep(2)
        raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")

    @staticmethod
    def _select_image(history_entry: dict, preferred_output_nodes: list[str]) -> ComfyImageRef:
        outputs = history_entry.get("outputs", {})
        ordered_node_ids: list[str] = []
        ordered_node_ids.extend([node_id for node_id in preferred_output_nodes if node_id in outputs])
        ordered_node_ids.extend([node_id for node_id in outputs.keys() if node_id not in ordered_node_ids])

        for node_id in ordered_node_ids:
            node_output = outputs.get(node_id, {})
            images = node_output.get("images", [])
            if images:
                first = images[0]
                return ComfyImageRef(
                    filename=first["filename"],
                    subfolder=first.get("subfolder", ""),
                    type=first.get("type", "output"),
                )

        raise RuntimeError("No images found in ComfyUI history output")

