# Reference Scene Style Cleanup Design

## Goal

Make `/generate/reference-scene` automatically remove the main subject from every uploaded style reference image before the reference is passed into Qwen Edit, so the generated candidate scene borrows scene mood and lighting without copying the reference image's own product.

## Constraints

- Keep the existing `/generate/reference-scene` endpoint and response shape.
- Cleanup is default behavior, not user-configurable.
- If cleanup is weak or fails, continue generation instead of failing the request.
- Persist debug artifacts and expose cleanup status in response metadata.

## Design

Add a new helper module dedicated to style reference cleanup. For each style reference:

1. Load the original reference image.
2. Reuse existing RMBG-based `extract_cutout_rgba` to estimate the reference subject.
3. Convert the cutout alpha to a binary mask, expand and feather the mask, and compute reliability heuristics.
4. Use local OpenCV inpainting to remove the masked subject from the reference image.
5. Save the expanded mask and cleaned reference image as debug artifacts.
6. Return the cleaned image plus per-reference metadata.

The main `reference-scene` route will replace raw `style_reference_images` with the cleaned images before calling `run_qwen_edit`, and it will merge cleanup summary metadata into the existing response metadata payload.

## Reliability Rules

- `cleanup_applied`: true when a cleaned reference image is actually generated and used.
- `cleanup_reliable`: true when the subject mask has a plausible area and does not excessively touch image borders.
- On extraction or cleanup failure, the route falls back to the original reference image and records the failure in metadata.

## Testing

- Unit-test cleanup on a synthetic image where a centered subject should be removed.
- Unit-test fallback behavior when subject extraction fails.
- Unit-test that summary metadata exposes applied/reliable flags and debug paths.
