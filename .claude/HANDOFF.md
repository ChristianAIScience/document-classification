# Handoff: docclass, 2026-11-17

Repo: `C:\Programming\document-classification`, remote `origin` (GitHub), branch `master`. Answer the user in German;
they approve commits, pushes and costly LLM runs explicitly.

## Read first (not duplicated here)

- `.claude/CLAUDE.md`: project conventions, Windows Smart App Control gotchas, evaluation rules.
- `README.md`: commands, API, data model, Task A and Task B evaluation, matching rules.
- `.claude/testset-mlflow-guide.md`: test set schema and metric definitions (Task A section 3A, Task B section 3B).
- `git log`: `d9e3bc3` pipeline, `bb74238` Task B (pushed). The code review fixes below are **uncommitted**.

## Uncommitted: code review fixes (9 of 10 findings; #5 deliberately not changed)

- Deviation matching (`pipeline/deviation.py`): compact normalization for exact matches; fuzzy only for long
  descriptions, same unit, ratio ≥ 0.9; global best-first assignment.
- `repository.verknuepfbar()` mirrors the DB link rules and is used for `link_ok`; `_link_angebot` rebuilds links
  pointing at a document, so a changed quote number no longer leaves stale `angebot_id`s. Clear 409 message when an
  invoice has no quote number.
- Evaluation: a crashed pair counts as wrong (`score_failed_pair`), never as TN. The extraction cache key includes
  system prompt and output schema, and cache writes are atomic. `process_pdf(extractor=…)` replaces the duplicated
  `extract_pdf`, so the evaluation runs exactly the production steps.
- Regression tests in `tests/test_review_fixes.py` and `tests/test_deviation.py`. Suite: 291 passed, ruff clean.
- The 100 cache entries were renamed to the new key format (they were produced with the current prompt and schema).
- Not changed (finding #5): `score_pair` scores only `pred[0]`, as the guide prescribes. Proposed instead: an extra
  metric "set of deviations exactly equal". Not implemented yet.

## Results (MLflow, http://localhost:5000)

- Task A (`document-extraction-eval`): every metric 1.0 except `acc_location` 0.0 (ground truth keeps only
  "Empfang EG"; the PDF prints the full address, so this is an annotation convention). Unchanged after the fixes
  (run `review-fixes`).
- Task B (`document-deviation-eval`): precision, recall and F1 1.0, tp 15, tn 35, fp 0, fn 0, `link_accuracy` 1.0,
  on ground truth and on real extraction. Unchanged after the fixes (runs `review-fixes-ground-truth`,
  `review-fixes-extraction`).
- 100 % is optimistic: one layout, one trade, digital PDFs, at most one deviation per invoice, 15 positives.

## Next steps

1. Ask the user before committing or pushing the review fixes.
2. Open decisions: the `acc_location` convention; the extra set-equality metric for Task B (finding #5);
   optionally `uv run docclass process data\testset --save` (no LLM cost because of the cache).

## Environment state

- PostgreSQL local, DB `auftrags_db`, Alembic head `1b33141ee96c`; contents: pair 0005 (1 supplier, 2 documents).
- MLflow server: Docker container `docclass-mlflow` (`docker compose up -d mlflow`). The old local `mlflow.db` and
  `mlruns/` were deleted.
- Credentials live in `.env` (not in git). Do not print them.
- Run Python only via `uv run …`. Start the API with `uv run python -m uvicorn docclass.api.app:app`, because
  `uvicorn.exe` is blocked.

## Suggested skills

- `mattpocock-skills:tdd`: for further fixes to matching or extraction (reproduce with a failing test first).
- `code-review`: review the uncommitted diff before committing.
- `mattpocock-skills:writing-for-agents`: when editing `.claude/CLAUDE.md` or this file.
