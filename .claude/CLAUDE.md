# CLAUDE.md

## Project: docclass

Incoming quotes (Angebote) and invoices (Rechnungen) as PDF → Docling Markdown → rule-based type
classification → LLM field extraction (`ExtractedDokument`) → Decimal validation → PostgreSQL.
Package in `src/docclass/` (pipeline, db, api), evaluation in `evaluation/`, overview and commands in `README.md`.

**Domain**
- The documents are sent *to* us (MusterAI GmbH, always the recipient). The counterparty is the **Lieferant**
  (sender); `kundennummer` is our customer number at that supplier.
- Domain identifiers are German (`dokumente`, `nummer`, `netto`), code comments and docstrings English.
- Money and quantities are `Decimal` end to end, rounded `ROUND_HALF_UP`, parsed through `Betrag`/`Datum` in
  `schemas.py` (they also accept German formats).
- `schemas.py` is shared by API, pipeline and LLM: field descriptions there are extraction instructions. Changing
  them or `SYSTEM_PROMPT` means bumping `PROMPT_VERSION` in `pipeline/extraction.py`.

**Database**
- Every model change ships as an Alembic migration: autogenerate, review the file, `alembic upgrade head`, then
  `alembic check` shows no drift. `migrations/env.py` limits Alembic to our own tables; the legacy tables
  (`kunden*`) in the dev database stay untouched.
- Writes that flush before commit run inside `write_or_conflict` (`api/errors.py`) so integrity errors become 409.

**Environment gotchas (Windows Smart App Control)**
- Native DLLs of `docling-parse` and `pyarrow` are blocked. Conversion uses the pypdfium2 backend; evaluation uses
  `mlflow-skinny`. Any dependency that pulls in `pyarrow` breaks the Docling import (pandas loads it) – check with
  `uv tree --all-groups --invert --package pyarrow` after dependency changes.
- Use the Bash tool with `uv run …`; there is no global `python` on PATH.

**Tests and evaluation**
- `uv run pytest` runs offline: SQLite in-memory, Markdown fixtures in `tests/fixtures/`, LLM mocked. Keep it so.
- `data/testset/` is a frozen ground-truth set; read it, never regenerate or edit it. Its rules, JSON schema and
  metric definitions: `.claude/testset-mlflow-guide.md` – read it before changing anything in `evaluation/`.
- Every change to conversion, classification, prompt or schema gets an evaluation run
  (`uv run --group eval python -m evaluation.run_extraction --run-name <name>`) and is compared against the
  previous run in MLflow. The tracking server runs in Docker (`docker compose up -d mlflow`, port 5000). Docling output is cached in `data/markdown_cache/` by PDF hash; delete the cache when
  conversion settings change.

---

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
