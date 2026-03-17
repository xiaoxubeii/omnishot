#!/usr/bin/env python3
import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_OUT = ROOT_DIR / "workflows" / "flux_product_demo.template.json"
DEFAULT_BINDINGS_OUT = ROOT_DIR / "workflows" / "flux_product_demo.bindings.json"

IMAGE_CLASS_HINTS = ("LoadImage", "ImageLoader", "LoadImageFromPath")
PROMPT_CLASS_HINTS = ("CLIPTextEncode", "TextEncode", "Prompt")
OUTPUT_CLASS_HINTS = ("SaveImage", "ImageSave", "WebsocketImageSave")
SAMPLER_CLASS_HINTS = ("KSampler", "Sampler", "RandomNoise")
PROMPT_INPUT_KEYS = ("text", "prompt", "clip_l", "t5xxl")
SEED_INPUT_KEYS = ("seed", "noise_seed", "rng_seed")
NEGATIVE_TEXT_HINTS = (
    "negative",
    "worst",
    "bad",
    "blurry",
    "deformed",
    "lowres",
    "low quality",
    "artifact",
    "nsfw",
)


def load_workflow(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Workflow is not a JSON object: {path}")
    return payload


def _ordered_node_items(workflow: dict) -> list[tuple[str, dict]]:
    def key_fn(item: tuple[str, dict]) -> tuple[int, str]:
        node_id = item[0]
        if node_id.isdigit():
            return (0, f"{int(node_id):010d}")
        return (1, node_id)

    return sorted(workflow.items(), key=key_fn)


def _class_type(node: dict) -> str:
    value = node.get("class_type", "")
    return value if isinstance(value, str) else ""


def _inputs(node: dict) -> dict:
    value = node.get("inputs", {})
    return value if isinstance(value, dict) else {}


def _is_link_value(value) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in hints)


def find_image_target(workflow: dict) -> list[dict]:
    candidates: list[tuple[str, str, str]] = []
    fallback: list[tuple[str, str, str]] = []

    for node_id, node in _ordered_node_items(workflow):
        class_type = _class_type(node)
        inputs = _inputs(node)
        if "image" not in inputs:
            continue

        target = (node_id, "image", class_type)
        if _contains_any(class_type, IMAGE_CLASS_HINTS):
            candidates.append(target)
        elif isinstance(inputs.get("image"), str):
            fallback.append(target)

    chosen = candidates[:1] if candidates else fallback[:1]
    return [{"node_id": node_id, "input_name": input_name} for node_id, input_name, _ in chosen]


def _prompt_candidates(workflow: dict) -> list[dict]:
    result: list[dict] = []
    for node_id, node in _ordered_node_items(workflow):
        class_type = _class_type(node)
        if not _contains_any(class_type, PROMPT_CLASS_HINTS):
            continue
        inputs = _inputs(node)
        fields: list[tuple[str, str]] = []
        for input_name in PROMPT_INPUT_KEYS:
            if input_name in inputs:
                text = inputs.get(input_name, "")
                text = text if isinstance(text, str) else ""
                fields.append((input_name, text))
        if fields:
            result.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "fields": fields,
                    "negative_score": _negative_score(" ".join(text for _, text in fields)),
                }
            )
    return result


def _negative_score(text: str) -> int:
    lowered = text.lower()
    return sum(1 for hint in NEGATIVE_TEXT_HINTS if hint in lowered)


def find_prompt_targets(workflow: dict) -> tuple[list[dict], list[dict]]:
    candidates = _prompt_candidates(workflow)
    if not candidates:
        return [], []

    negative_node = None
    highest_score = 0
    for node in candidates:
        score = node["negative_score"]
        if score > highest_score:
            highest_score = score
            negative_node = node

    if highest_score <= 0:
        negative_node = None

    positive_node = None
    for node in candidates:
        if negative_node is not None and node["node_id"] == negative_node["node_id"]:
            continue
        positive_node = node
        break

    if positive_node is None:
        positive_node = candidates[0]

    if negative_node is None and len(candidates) > 1:
        for node in candidates:
            if node["node_id"] != positive_node["node_id"]:
                negative_node = node
                break

    def node_to_targets(node: dict | None) -> list[dict]:
        if node is None:
            return []
        return [
            {"node_id": node["node_id"], "input_name": input_name}
            for input_name, _ in node["fields"]
        ]

    return node_to_targets(positive_node), node_to_targets(negative_node)


def find_seed_targets(workflow: dict) -> list[dict]:
    candidates: list[tuple[str, str, str]] = []
    fallback: list[tuple[str, str, str]] = []

    for node_id, node in _ordered_node_items(workflow):
        class_type = _class_type(node)
        inputs = _inputs(node)
        for seed_key in SEED_INPUT_KEYS:
            if seed_key not in inputs:
                continue
            target = (node_id, seed_key, class_type)
            if _contains_any(class_type, SAMPLER_CLASS_HINTS):
                candidates.append(target)
            else:
                fallback.append(target)

    chosen = candidates[:1] if candidates else fallback[:1]
    return [{"node_id": node_id, "input_name": input_name} for node_id, input_name, _ in chosen]


def find_output_nodes(workflow: dict) -> list[str]:
    preferred: list[str] = []
    fallback: list[str] = []

    for node_id, node in _ordered_node_items(workflow):
        class_type = _class_type(node)
        inputs = _inputs(node)

        if "images" not in inputs:
            continue
        if not _is_link_value(inputs.get("images")):
            continue

        if _contains_any(class_type, OUTPUT_CLASS_HINTS):
            preferred.append(node_id)
        else:
            fallback.append(node_id)

    # Prefer the last save-like node as final output, since many workflows
    # keep intermediate SaveImage nodes before the true final composite.
    if preferred:
        return [preferred[-1]]
    return fallback[-1:] if fallback else []


def build_bindings(workflow: dict) -> dict:
    positive_prompt, negative_prompt = find_prompt_targets(workflow)
    return {
        "image": find_image_target(workflow),
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "seed": find_seed_targets(workflow),
        "preferred_output_nodes": find_output_nodes(workflow),
    }


def print_summary(workflow: dict, bindings: dict) -> None:
    print(f"workflow_nodes: {len(workflow)}")
    print("detected_bindings:")
    for key in ("image", "positive_prompt", "negative_prompt", "seed", "preferred_output_nodes"):
        print(f"  - {key}: {bindings.get(key)}")


def print_node_table(workflow: dict) -> None:
    print("\nnode_overview:")
    for node_id, node in _ordered_node_items(workflow):
        class_type = _class_type(node)
        input_keys = list(_inputs(node).keys())
        print(f"  - id={node_id} class={class_type} inputs={input_keys}")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate bindings json from a ComfyUI API workflow export.",
    )
    parser.add_argument(
        "--workflow",
        type=Path,
        required=True,
        help="Path to your exported ComfyUI API JSON file.",
    )
    parser.add_argument(
        "--write-template",
        type=Path,
        default=DEFAULT_TEMPLATE_OUT,
        help=f"Where to copy the workflow template (default: {DEFAULT_TEMPLATE_OUT})",
    )
    parser.add_argument(
        "--write-bindings",
        type=Path,
        default=DEFAULT_BINDINGS_OUT,
        help=f"Where to write bindings json (default: {DEFAULT_BINDINGS_OUT})",
    )
    parser.add_argument(
        "--skip-template-copy",
        action="store_true",
        help="Do not overwrite template json; only generate bindings.",
    )
    parser.add_argument(
        "--print-nodes",
        action="store_true",
        help="Print all nodes (id, class_type, input keys) for manual inspection.",
    )
    args = parser.parse_args()

    if not args.workflow.exists():
        print(f"ERROR: workflow file not found: {args.workflow}")
        return 1

    workflow = load_workflow(args.workflow)
    bindings = build_bindings(workflow)

    if not args.skip_template_copy:
        source_path = args.workflow.resolve()
        target_path = args.write_template.resolve()
        if source_path == target_path:
            print(f"template_unchanged: {args.write_template} (source and target are identical)")
        else:
            args.write_template.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.workflow, args.write_template)
            print(f"template_written: {args.write_template}")

    write_json(args.write_bindings, bindings)
    print(f"bindings_written: {args.write_bindings}")
    print_summary(workflow, bindings)

    if args.print_nodes:
        print_node_table(workflow)

    if not bindings["image"] or not bindings["preferred_output_nodes"]:
        print("\nWARNING: Could not confidently detect required nodes. Use --print-nodes and edit bindings.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
