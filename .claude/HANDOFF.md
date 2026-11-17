# Handoff: docclass, Task B (deviation detection), 2026-11-17

Repo: `C:\Programming\document-classification`. Answer the user in German; they approve commits and costly LLM
runs explicitly.

## Read first (not duplicated here)

- `.claude/CLAUDE.md`: project conventions, Windows Smart App Control gotchas, evaluation rules.
- `README.md`: commands, API, data model, Task A and Task B evaluation.
- `.claude/testset-mlflow-guide.md`: test set schema and metric definitions (Task A section 3A, Task B section 3B).
- `git log` / `git diff`: last commit `d9e3bc3`; all Task B work is **uncommitted** (see below).

## What this session did after `d9e3bc3` (uncommitted)

Task B: detect deviations between a quote and its invoice.

- `src/docclass/pipeline/deviation.py`: deterministic comparison. Positions are matched by description (exact,
  then `SequenceMatcher` ≥ 0.85) because invoices are renumbered after an `item_missing`. Emits
  `price_changed`, `quantity_changed`, `item_missing`, `item_added` (type codes equal the test set's).
- `Abweichung` schema in `src/docclass/schemas.py`. Endpoint `GET /api/dokumente/{id}/abweichungen` computes the
  deviations from stored positions; returns 409 for non-invoices or invoices without a linked quote.
- `evaluation/extraction_cache.py`: disk cache for LLM extraction (`data/extraction_cache/`, gitignored), with
  `extract_pdf()` shared by Task A (`run_extraction.py` now uses it) and Task B.
- `evaluation/run_deviation.py`: MLflow experiment `document-deviation-eval`, `--source ground-truth|extraction`.
- `evaluation/metrics.py`: `score_pair` / `summarize_pairs` per the guide; `mapping.py`: `abweichung_to_truth_format`.
- Tests: `tests/test_deviation.py` (all 50 ground-truth pairs reproduce exactly, plus fuzzy-match, double-change,
  missing/added and metrics cases) and two API tests in `tests/test_api.py`. Suite: 277 passed, ruff clean.
- README and CLAUDE.md updated for Task B and the extraction cache.

## Results

- Task A baseline, experiment `document-extraction-eval`, run `hybrid-gpt-4.1-mini-v1`: every metric 1.0
  except `acc_location` 0.0 (ground truth keeps only "Empfang EG"; the PDF prints the full address, so this is an
  annotation convention, not an extraction error). 100 % is optimistic: one layout, one trade, digital PDFs only.
- MLflow run `logic-ground-truth` (experiment 2, http://localhost:5000/#/experiments/2): all 1.0, tp 15, tn 35,
  fp 0, fn 0. The comparison logic is correct given perfect extraction.
- MLflow run `hybrid-gpt-4.1-mini-v1` (`--source extraction`, real PDFs): also all 1.0, tp 15, tn 35, fp 0,
  fn 0, `link_accuracy` 1.0, 0 errors. All 100 extractions are cached in `data/extraction_cache/`, so reruns of
  Task A/B with unchanged model and prompt cost no LLM calls.

## Next steps

1. Ask the user before committing the Task B work.
2. Still open from before: the `acc_location` = 0 % convention decision; deleting the old local `mlflow.db` and
   `mlruns/` (awaiting user confirmation); optionally `uv run docclass process data\testset --save`.

## Environment state

- PostgreSQL local, DB `auftrags_db`, Alembic head `1b33141ee96c`; contents: pair 0005 (1 supplier, 2 documents).
- MLflow server: Docker container `docclass-mlflow` (`docker compose up -d mlflow`).
- Credentials live in `.env` (not in git). Do not print them.
- Run Python only via `uv run …`. Start the API with `uv run python -m uvicorn docclass.api.app:app`, because
  `uvicorn.exe` is blocked.

## Suggested skills

- `mattpocock-skills:tdd`: for any fix to matching or extraction found in step 1 (reproduce with a failing test first).
- `mattpocock-skills:diagnosing-bugs`: if extraction-mode Task B shows misses whose cause is unclear.
- `code-review`: review the uncommitted Task B diff before committing.
- `mattpocock-skills:writing-for-agents`: when editing `.claude/CLAUDE.md` or `.claude/HANDOFF.md`.
