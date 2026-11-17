"""Task A evaluation (extraction per document) against data/testset, logged to MLflow.

    uv run --group eval python -m evaluation.run_extraction [--limit N] [--run-name NAME] [--classification-only]

One run per system version (model, prompt, pipeline); compare runs in the MLflow UI. The test set is frozen;
its hash is logged with every run.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import mlflow
import pandas as pd

from docclass.core.config import settings
from docclass.pipeline.classification import classify
from docclass.pipeline.conversion import pdf_to_markdown
from evaluation.mapping import to_truth_format
from evaluation.metrics import EXTRA_FIELDS, FIELDS, score_extraction, score_items

EXPERIMENT = "document-extraction-eval"


def testset_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.glob("*")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def evaluate_document(pdf: Path, truth: dict, classification_only: bool) -> dict:
    markdown = pdf_to_markdown(pdf)
    klassifikation = classify(markdown)
    row = {
        "file": pdf.name,
        "true_type": truth["doc_type"],
        "rule_type": klassifikation.dokumententyp,
        "rule_confidence": klassifikation.konfidenz,
        "rule_type_ok": klassifikation.dokumententyp == truth["doc_type"],
    }
    if classification_only:
        return row

    from docclass.pipeline.extraction import extract
    from docclass.pipeline.service import resolve_typ
    from docclass.pipeline.validation import validate

    try:
        dokument, warnungen = resolve_typ(
            klassifikation, extract(markdown, dokumententyp_hint=klassifikation.dokumententyp),
        )
    except Exception as exc:  # noqa: BLE001  one failing document must not abort the run
        row["error"] = f"{type(exc).__name__}: {exc}"[:500]
        row.update({f: False for f in FIELDS + EXTRA_FIELDS})
        row.update({"items_count": False, "items_totals": False, "items_exact": False, "valid": False})
        return row

    pred = to_truth_format(dokument)
    warnungen += validate(dokument)
    row.update(score_extraction(truth, pred, FIELDS + EXTRA_FIELDS))
    row.update(score_items(truth["items"], pred["items"]))
    row["valid"] = not warnungen
    row["warnings"] = "; ".join(warnungen)
    row["prediction"] = json.dumps(pred, ensure_ascii=False)
    row["error"] = None
    return row


def summarize(df: pd.DataFrame, classification_only: bool) -> dict[str, float]:
    metrics = {"rule_doc_type_accuracy": df.rule_type_ok.mean(), "rule_undecided": int(df.rule_type.isna().sum())}
    if classification_only:
        return metrics
    metrics |= {f"acc_{f.replace('.', '_')}": df[f].mean() for f in FIELDS + EXTRA_FIELDS}
    metrics |= {
        "exact_match_rate": df[FIELDS].all(axis=1).mean(),
        "doc_type_accuracy": df["doc_type"].mean(),
        "items_count_accuracy": df.items_count.mean(),
        "items_totals_accuracy": df.items_totals.mean(),
        "items_exact_accuracy": df.items_exact.mean(),
        "validation_pass_rate": df.valid.mean(),
        "error_count": int(df.error.notna().sum()),
    }
    return {k: float(v) for k, v in metrics.items()}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="nur die ersten N Dokumente (Smoke-Test)")
    parser.add_argument("--run-name")
    parser.add_argument("--classification-only", action="store_true", help="ohne LLM, nur Regel-Klassifikation")
    args = parser.parse_args()

    root = settings.testset_dir
    pdfs = sorted(root.glob("*.pdf"))[: args.limit]

    from docclass.pipeline.extraction import PROMPT_VERSION

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=args.run_name):
        mlflow.log_params({
            "testset_hash": testset_hash(root), "testset_seed": 42, "testset_pairs": 50, "n_documents": len(pdfs),
            "model": None if args.classification_only else settings.llm_model,
            "prompt_version": PROMPT_VERSION, "ocr": settings.ocr_enabled, "converter": "docling-pypdfium2",
            "classification_only": args.classification_only,
        })
        rows = []
        for i, pdf in enumerate(pdfs, 1):
            truth = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
            rows.append(evaluate_document(pdf, truth, args.classification_only))
            print(f"[{i}/{len(pdfs)}] {pdf.name}", file=sys.stderr)

        df = pd.DataFrame(rows)
        metrics = summarize(df, args.classification_only)
        mlflow.log_metrics(metrics)
        mlflow.log_table(df, artifact_file="document_results.json")

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
