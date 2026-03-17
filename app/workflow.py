import json
from copy import deepcopy
from pathlib import Path

from pydantic import BaseModel, Field


class WorkflowTarget(BaseModel):
    node_id: str
    input_name: str


class WorkflowBindings(BaseModel):
    image: list[WorkflowTarget]
    positive_prompt: list[WorkflowTarget]
    negative_prompt: list[WorkflowTarget] = Field(default_factory=list)
    seed: list[WorkflowTarget] = Field(default_factory=list)
    preferred_output_nodes: list[str] = Field(default_factory=list)


def load_workflow_template(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Workflow file is not a JSON object: {path}")
    return payload


def load_workflow_bindings(path: Path) -> WorkflowBindings:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return WorkflowBindings.model_validate(payload)


def _set_targets(workflow: dict, targets: list[WorkflowTarget], value, label: str) -> None:
    for target in targets:
        node = workflow.get(target.node_id)
        if node is None:
            raise KeyError(f"Missing workflow node for {label}: {target.node_id}")
        inputs = node.setdefault("inputs", {})
        inputs[target.input_name] = value


def build_workflow(
    template_path: Path,
    bindings_path: Path,
    image_name: str,
    prompt: str,
    negative_prompt: str,
    seed: int | None,
) -> tuple[dict, WorkflowBindings]:
    workflow = deepcopy(load_workflow_template(template_path))
    bindings = load_workflow_bindings(bindings_path)

    _set_targets(workflow, bindings.image, image_name, "image")
    _set_targets(workflow, bindings.positive_prompt, prompt, "positive_prompt")

    if bindings.negative_prompt:
        _set_targets(workflow, bindings.negative_prompt, negative_prompt, "negative_prompt")

    if seed is not None and bindings.seed:
        _set_targets(workflow, bindings.seed, seed, "seed")

    return workflow, bindings


def inspect_workflow(template_path: Path, bindings_path: Path) -> dict:
    info = {
        "workflow_template_exists": template_path.exists(),
        "workflow_bindings_exists": bindings_path.exists(),
        "workflow_nodes": None,
        "workflow_binding_errors": [],
    }

    if not template_path.exists() or not bindings_path.exists():
        return info

    try:
        workflow = load_workflow_template(template_path)
        bindings = load_workflow_bindings(bindings_path)
        info["workflow_nodes"] = len(workflow)

        checks = {
            "image": bindings.image,
            "positive_prompt": bindings.positive_prompt,
            "negative_prompt": bindings.negative_prompt,
            "seed": bindings.seed,
        }
        for label, targets in checks.items():
            for target in targets:
                if target.node_id not in workflow:
                    info["workflow_binding_errors"].append(
                        f"{label}: node {target.node_id} not found in workflow"
                    )
    except Exception as exc:
        info["workflow_binding_errors"].append(str(exc))

    return info

