# Handoff: docclass, 2026-11-17

Repo: `C:\Programming\document-classification`, remote `origin` (GitHub), branch `master`, clean and pushed.
Answer the user in German; they approve commits, pushes and costly LLM runs explicitly.

## Read first (not duplicated here)

- `.claude/CLAUDE.md`: project conventions, Windows Smart App Control gotchas, test and evaluation rules.
- `README.md`: commands, API, data model, Task A and Task B evaluation, matching rules, test commands.
- `.claude/testset-mlflow-guide.md`: test set schema and metric definitions (Task A section 3A, Task B section 3B).
- `git log`: `d9e3bc3` pipeline, `bb74238` Task B, `72029fd` code review fixes and PostgreSQL integration tests.

## Done

- Pipeline PDF → Docling Markdown → rule classification → LLM extraction → validation → PostgreSQL, with upload
  API and CLI.
- Task A (extraction) and Task B (deviation detection between quote and invoice) with MLflow evaluation.
- Code review: 9 of 10 findings fixed (commit `72029fd`). Finding #5 deliberately unchanged: `score_pair` scores
  only `pred[0]`, as the guide prescribes.
- Tests: `uv run pytest` → 291 passed, offline. `uv run pytest -m postgres` → 19 passed against a throwaway
  database on the real server (migration ↔ models, downgrade/upgrade, constraints, API tests on PostgreSQL).

## Results (MLflow, http://localhost:5000)

- Task A (`document-extraction-eval`): every metric 1.0 except `acc_location` 0.0 (ground truth keeps only
  "Empfang EG"; the PDF prints the full address, so this is an annotation convention). Latest run `review-fixes`.
- Task B (`document-deviation-eval`): precision, recall and F1 1.0, tp 15, tn 35, fp 0, fn 0, `link_accuracy` 1.0,
  on ground truth and on real extraction. Latest runs `review-fixes-ground-truth`, `review-fixes-extraction`.
- 100 % is optimistic: one layout, one trade, digital PDFs, at most one deviation per invoice, 15 positives.
- All 100 LLM extractions are cached in `data/extraction_cache/`, so reruns with unchanged model, prompt and
  schema cost no LLM calls.

## Open decisions (ask the user)

1. `acc_location`: adapt the prompt to the annotation convention, or accept the gap.
2. Task B extra metric "set of deviations exactly equal" (finding #5 alternative); not implemented.
3. Optionally load all test documents into the dev DB: `uv run docclass process data\testset --save`
   (no LLM cost because of the cache).
4. Broader robustness: a test set with other layouts or scans, then compare runs in MLflow.

## Environment state

- PostgreSQL local, DB `auftrags_db`, Alembic head `1b33141ee96c`; contents: pair 0005 (1 supplier, 2 documents).
- MLflow server: Docker container `docclass-mlflow` (`docker compose up -d mlflow`).
- Credentials live in `.env` (not in git). Do not print them.
- Run Python only via `uv run …`. Start the API with `uv run python -m uvicorn docclass.api.app:app`, because
  `uvicorn.exe` is blocked.

## Suggested skills

- `mattpocock-skills:tdd`: for further fixes to matching or extraction (reproduce with a failing test first).
- `code-review`: review a diff before committing.
- `mattpocock-skills:writing-for-agents`: when editing `.claude/CLAUDE.md` or this file.
