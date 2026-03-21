from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


_WIDGET_VALUE_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN"}
_LINK_ONLY_TYPES = {
    "MODEL",
    "CLIP",
    "CONDITIONING",
    "LATENT",
    "IMAGE",
    "MASK",
    "VAE",
    "CONTROL_NET",
    "GUIDER",
    "SAMPLER",
    "SIGMAS",
    "NOISE",
    "AUDIO",
    "VIDEO",
}


def load_frontend_workflow(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or "nodes" not in payload:
        raise ValueError(f"Expected a ComfyUI frontend workflow JSON object: {path}")
    return payload


def _normalize_schema_input_order(schema: dict[str, Any]) -> list[str]:
    input_order = schema.get("input_order", {})
    ordered: list[str] = []
    for bucket in ("required", "optional"):
        ordered.extend(input_order.get(bucket, []))

    if ordered:
        return ordered

    input_spec = schema.get("input", {})
    for bucket in ("required", "optional"):
        ordered.extend((input_spec.get(bucket) or {}).keys())
    return ordered


def _lookup_schema_input(schema: dict[str, Any], input_name: str) -> Any:
    input_spec = schema.get("input", {})
    for bucket in ("required", "optional"):
        bucket_spec = input_spec.get(bucket) or {}
        if input_name in bucket_spec:
            return bucket_spec[input_name]
    return None


def _schema_input_uses_widget(schema_input: Any) -> bool:
    if not isinstance(schema_input, list) or not schema_input:
        return False
    input_type = schema_input[0]
    if isinstance(input_type, list):
        return True
    if input_type in _WIDGET_VALUE_TYPES:
        return True
    if isinstance(input_type, str) and input_type not in _LINK_ONLY_TYPES:
        return True
    return False


def _schema_input_options(schema_input: Any) -> dict[str, Any]:
    if isinstance(schema_input, list) and len(schema_input) > 1 and isinstance(schema_input[1], dict):
        return schema_input[1]
    return {}


def _input_uses_widget(input_meta: dict[str, Any] | None, schema_input: Any) -> bool:
    if input_meta is not None and "widget" in input_meta:
        return True
    return _schema_input_uses_widget(schema_input)


def _normalize_link_ref(raw_link: Any, links_by_id: dict[int, list[Any]]) -> list[Any] | None:
    if raw_link is None:
        return None
    if isinstance(raw_link, list) and len(raw_link) == 2:
        return [str(raw_link[0]), raw_link[1]]
    if isinstance(raw_link, int):
        link = links_by_id.get(raw_link)
        if link is None:
            raise KeyError(f"Missing link definition for link id {raw_link}")
        return [str(link[1]), link[2]]
    return None


def convert_frontend_workflow_to_api(
    frontend_workflow: dict[str, Any],
    object_info: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    nodes = frontend_workflow.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Frontend workflow is missing a nodes list")

    links = frontend_workflow.get("links", [])
    links_by_id = {
        int(link[0]): link
        for link in links
        if isinstance(link, list) and len(link) >= 5 and isinstance(link[0], int)
    }

    workflow: dict[str, dict[str, Any]] = {}

    for node in nodes:
        node_id = str(node["id"])
        class_type = str(node["type"])
        schema = object_info.get(class_type, {})
        ordered_inputs = _normalize_schema_input_order(schema)
        node_inputs = {item["name"]: item for item in node.get("inputs", []) if isinstance(item, dict) and "name" in item}
        widget_values = list(node.get("widgets_values") or [])
        widget_index = 0
        api_inputs: dict[str, Any] = {}

        consumed_names: set[str] = set()
        for input_name in ordered_inputs:
            consumed_names.add(input_name)
            schema_input = _lookup_schema_input(schema, input_name)
            schema_options = _schema_input_options(schema_input)
            input_meta = node_inputs.get(input_name)
            uses_widget = _input_uses_widget(input_meta, schema_input)
            linked_value = _normalize_link_ref(input_meta.get("link") if input_meta else None, links_by_id)

            if linked_value is not None:
                api_inputs[input_name] = linked_value
                if uses_widget and widget_index < len(widget_values):
                    widget_index += 1
                continue

            if uses_widget and widget_index < len(widget_values):
                api_inputs[input_name] = widget_values[widget_index]
                widget_index += 1
                if (
                    schema_options.get("control_after_generate") is True
                    and "control_after_generate" not in ordered_inputs
                    and "control_after_generate" not in api_inputs
                    and widget_index < len(widget_values)
                ):
                    api_inputs["control_after_generate"] = widget_values[widget_index]
                    widget_index += 1

        for input_name, input_meta in node_inputs.items():
            if input_name in consumed_names:
                continue
            linked_value = _normalize_link_ref(input_meta.get("link"), links_by_id)
            if linked_value is not None:
                api_inputs[input_name] = linked_value

        workflow[node_id] = {
            "class_type": class_type,
            "inputs": api_inputs,
        }

    return workflow


def _schema_choices(object_info: dict[str, Any], class_type: str, input_name: str) -> list[Any]:
    schema = object_info.get(class_type, {})
    schema_input = _lookup_schema_input(schema, input_name)
    if isinstance(schema_input, list) and schema_input and isinstance(schema_input[0], list):
        return list(schema_input[0])
    return []


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)


def _replace_link_refs(workflow: dict[str, dict[str, Any]], source_node_id: str, output_index: int, replacement: Any) -> None:
    for node in workflow.values():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for input_name, value in list(inputs.items()):
            if value == [source_node_id, output_index]:
                inputs[input_name] = deepcopy(replacement)


def _delete_node(workflow: dict[str, dict[str, Any]], node_id: str) -> None:
    workflow.pop(node_id, None)


def _best_choice(current: Any, choices: list[Any]) -> Any:
    if not choices:
        return current
    if current in choices:
        return current
    if not isinstance(current, str):
        return choices[0]

    current_lower = current.lower()
    for choice in choices:
        if isinstance(choice, str) and choice.lower() == current_lower:
            return choice

    normalized_current = current_lower.replace(".safetensors", "").replace(".gguf", "")
    for choice in choices:
        if not isinstance(choice, str):
            continue
        normalized_choice = choice.lower().replace(".safetensors", "").replace(".gguf", "")
        if normalized_choice == normalized_current:
            return choice
        if normalized_current in normalized_choice or normalized_choice in normalized_current:
            return choice

    if "t5" in normalized_current:
        for choice in choices:
            if isinstance(choice, str) and "t5" in choice.lower():
                return choice
    if "kontext" in normalized_current:
        for choice in choices:
            if isinstance(choice, str) and "kontext" in choice.lower():
                return choice
    if "clip" in normalized_current:
        for choice in choices:
            if isinstance(choice, str) and "clip" in choice.lower():
                return choice
    if "kontext" in normalized_current or "flux1" in normalized_current:
        for choice in choices:
            if isinstance(choice, str) and "flux1" in choice.lower():
                return choice

    return choices[0]


def _prune_unreachable_nodes(workflow: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output_node_ids = [
        node_id
        for node_id, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == "SaveImage"
    ]
    if not output_node_ids:
        return workflow

    reachable: set[str] = set()
    stack = list(output_node_ids)
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        node = workflow.get(node_id, {})
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for value in inputs.values():
            if _is_link(value):
                stack.append(value[0])

    return {node_id: node for node_id, node in workflow.items() if node_id in reachable}


def adapt_api_workflow_for_local_runtime(
    workflow: dict[str, dict[str, Any]],
    object_info: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    adapted = deepcopy(workflow)
    downgraded_from_kontext = False
    reference_latent_inputs: dict[str, Any] | None = None

    for node_id, node in list(adapted.items()):
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        if class_type == "DualCLIPLoader":
            clip_choices = _schema_choices(object_info, "DualCLIPLoader", "clip_name1")
            inputs["clip_name1"] = _best_choice(inputs.get("clip_name1"), clip_choices)
            inputs["clip_name2"] = _best_choice(inputs.get("clip_name2"), clip_choices)
            continue

        if class_type == "UNETLoader":
            current_name = inputs.get("unet_name")
            native_choices = _schema_choices(object_info, "UNETLoader", "unet_name")
            if current_name not in native_choices:
                gguf_choices = _schema_choices(object_info, "UnetLoaderGGUF", "unet_name")
                if gguf_choices:
                    chosen_name = _best_choice(current_name, gguf_choices)
                    node["class_type"] = "UnetLoaderGGUF"
                    node["inputs"] = {"unet_name": chosen_name}
                    downgraded_from_kontext = "kontext" not in str(chosen_name).lower()
            continue

        if class_type == "LoraLoader":
            lora_choices = _schema_choices(object_info, "LoraLoader", "lora_name")
            if inputs.get("lora_name") not in lora_choices:
                _replace_link_refs(adapted, node_id, 0, inputs.get("model"))
                _replace_link_refs(adapted, node_id, 1, inputs.get("clip"))
                _delete_node(adapted, node_id)
            continue

        if class_type == "LibLibTranslate" and class_type not in object_info:
            _replace_link_refs(adapted, node_id, 0, "")
            _delete_node(adapted, node_id)
            continue

        if class_type == "ReferenceLatent":
            reference_latent_inputs = deepcopy(inputs)

    if downgraded_from_kontext and reference_latent_inputs is not None:
        for node_id, node in list(adapted.items()):
            if node.get("class_type") != "ReferenceLatent":
                continue
            conditioning = node.get("inputs", {}).get("conditioning")
            latent = node.get("inputs", {}).get("latent")
            _replace_link_refs(adapted, node_id, 0, conditioning)
            for consumer in adapted.values():
                consumer_inputs = consumer.get("inputs", {})
                if not isinstance(consumer_inputs, dict):
                    continue
                if consumer.get("class_type") == "KSampler" and consumer_inputs.get("latent_image") and latent:
                    consumer_inputs["latent_image"] = deepcopy(latent)
                    denoise = consumer_inputs.get("denoise")
                    if denoise == 1:
                        consumer_inputs["denoise"] = 0.55
            _delete_node(adapted, node_id)

    return _prune_unreachable_nodes(adapted)
