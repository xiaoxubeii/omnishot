# Reference Scene Style Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add default style-reference subject cleanup to the existing `reference-scene` generation flow and expose cleanup artifacts in metadata.

**Architecture:** Introduce a focused helper module for style-reference cleanup and keep `main.py` responsible only for request orchestration. The route will call the helper under the existing GPU lock, then pass cleaned reference images into the current Qwen Edit pipeline.

**Tech Stack:** FastAPI, Pillow, NumPy, OpenCV, unittest

---

### Task 1: Add failing tests for style-reference cleanup

**Files:**
- Create: `tests/test_reference_style_cleanup.py`
- Test: `tests/test_reference_style_cleanup.py`

- [ ] **Step 1: Write the failing tests**

Write tests for:
- successful cleanup on a synthetic reference image
- fallback to the original reference image when extraction fails
- summary metadata containing applied/reliable flags and artifact paths

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m unittest tests.test_reference_style_cleanup -v`
Expected: FAIL because the cleanup module/functions do not exist yet

### Task 2: Implement cleanup helper and wire route metadata

**Files:**
- Create: `app/reference_style_cleanup.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write minimal implementation**

Implement:
- subject mask expansion and feathering
- OpenCV inpainting
- reliability heuristics
- debug artifact persistence
- metadata summary builder

- [ ] **Step 2: Run tests to verify they pass**

Run: `./.venv/bin/python -m unittest tests.test_reference_style_cleanup -v`
Expected: PASS

### Task 3: Run broader verification and real smoke case

**Files:**
- Verify: `scripts/smoke_reference_scene.py`

- [ ] **Step 1: Run targeted smoke case**

Run the existing reference-scene smoke script with sample product and sample style reference.

- [ ] **Step 2: Confirm metadata and output artifacts**

Check:
- final output path exists
- candidate output path exists
- cleanup mask/cleaned files exist
- response metadata includes cleanup fields
