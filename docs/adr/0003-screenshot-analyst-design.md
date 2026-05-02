# Screenshot Analyst Sub-Agent Design

Screenshots captured during Browser test failures can show visible error messages that help identify root causes. We needed a design for a new screenshot analyst sub-agent that fits into the existing orchestrator pipeline alongside the RF failure analyst and the Playwright log analyst.

## Core decisions

**OCR-first with multimodal fallback.** We extract text via OCR and feed it to the LLM rather than sending the raw image directly. The pages under test are simple and well-contrasted, making OCR reliable for explicit error text. OCR output is auditable, deterministic, and cheaper than multimodal inference. Multimodal is only triggered when OCR quality falls below fixed thresholds (median confidence, low-confidence token ratio, character validity, high-signal keyword hit). When OCR and multimodal disagree, OCR is authoritative.

**Fixed quality thresholds.** Fallback routing decisions use fixed, configured thresholds rather than adaptive per-project learning. This keeps behavior deterministic across CI runs and makes tests stable.

**No guessing on low-quality images.** When OCR quality is below threshold and multimodal is unavailable, the analyst returns `no_evidence` with a reason code (`no_screenshots`, `screenshot_unreadable`). No root cause is inferred from unreadable data.

**Once per error group, not per test.** The analyst is invoked once per error group using the representative test's screenshots. The error group already captures that tests share the same failure pattern; per-test invocation would multiply cost for identical root causes.

**Skip when no screenshots exist.** When the representative test has no screenshot paths, the orchestrator skips the sub-agent entirely and records `no_screenshots`. This is the common case for network errors and timeouts that don't reach a screenshot step.

**Paths from orchestrator; failure detail on request.** Screenshot paths are passed directly from the orchestrator (already resolved by the RF results pipeline). The sub-agent does not re-derive them. However, calling `get_failure_detail` for broader failure context (log messages, keyword tree) is allowed and useful.

## Output contract

One JSON object per error group:

```json
{
  "test_id": "<representative test id>",
  "screenshot_text": "<raw OCR text or null>",
  "visible_error": "<extracted error message visible on screen or null>",
  "failure_area": "auth | navigation | validation | network | dialog | unknown",
  "confidence": "high | medium | low | no_evidence",
  "evidence_source": "ocr | multimodal | none",
  "reason": "<no_screenshots | screenshot_unreadable | null>"
}
```

Confidence rules:
- `high`: OCR text contains a visible error matching the RF failure message or a known error keyword (`error`, `failed`, `invalid`, `denied`, `timeout`).
- `medium`: OCR text is present and plausible but does not directly match the RF failure.
- `low`: OCR quality passed threshold but no clear failure signal found; or multimodal found only a weak visual cue.
- `no_evidence`: no screenshots, unreadable image, or OCR below threshold with no fallback.

## Implementation notes

OCR is implemented via `pytesseract` (Tesseract backend), isolated in `src/robotframework_analysis/agent/ocr.py` behind a single function `extract_text(path: Path) -> tuple[str, float]`. Tesseract was chosen for offline operation, native per-word confidence scores, and minimal dependency footprint. Replace by swapping `ocr.py` only — the agent and delegate are unaffected.
