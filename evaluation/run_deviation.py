"""Task B evaluation (deviation detection per quote/invoice pair) against data/testset, logged to MLflow.

    uv run --group eval python -m evaluation.run_deviation [--source extraction|ground-truth] [--limit N]

`--source ground-truth` feeds the annotated JSON into the comparison and measures the comparison logic alone
(no LLM). `--source extraction` runs the real pipeline per PDF; LLM results are cached in data/extraction_cache/.
"""

import argparse
import json
import sys

import mlflow
import pandas as pd

from docclass.core.config import settings
from docclass.pipeline.deviation import AEHNLICHKEIT_SCHWELLE, find_abweichungen
from docclass.pipeline.extraction import PROMPT_VERSION
from docclass.schemas import ExtractedDokument
from evaluation.mapping import abweichung_to_truth_format, from_truth_format
from evaluation.metrics import score_pair, summarize_pairs
from evaluation.run_extraction import testset_hash

EXPERIMENT = "document-deviation-eval"


def load_pair(pair_id: str, source: str) -> tuple[ExtractedDokument, ExtractedDokument]:
    def one(name: str) -> ExtractedDokument:
        if source == "ground-truth":
            return from_truth_format(json.loads((settings.testset_dir / f"{name}.json").read_text(encoding="utf-8")))
        from evaluation.extraction_cache import extract_pdf
        return extract_pdf(settings.testset_dir / f"{name}.pdf")[1]

    return one(f"angebot_{pair_id}"), one(f"rechnung_{pair_id}")


def evaluate_pair(pair_id: str, source: str) -> dict:
    truth = json.loads((settings.testset_dir / f"rechnung_{pair_id}.json").read_text(encoding="utf-8"))["deviations"]
    try:
        angebot, rechnung = load_pair(pair_id, source)
    except Exception as exc:  # noqa: BLE001  one failing pair must not abort the run
        return {"pair_id": pair_id, **score_pair(truth, []), "link_ok": False,
                "error": f"{type(exc).__name__}: {exc}"[:500]}

    pred = [abweichung_to_truth_format(a) for a in find_abweichungen(angebot.positionen, rechnung.positionen)]
    return {
        "pair_id": pair_id,
        **score_pair(truth, pred),
        # Would the DB link the invoice to this quote? (same quote number, same supplier VAT ID)
        "link_ok": rechnung.angebot_nummer == angebot.nummer and rechnung.lieferant.ust_id == angebot.lieferant.ust_id,
        "n_predicted": len(pred),
        "truth": json.dumps(truth, ensure_ascii=False),
        "prediction": json.dumps(pred, ensure_ascii=False),
        "error": None,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["extraction", "ground-truth"], default="extraction")
    parser.add_argument("--limit", type=int, help="nur die ersten N Paare (Smoke-Test)")
    parser.add_argument("--run-name")
    args = parser.parse_args()

    pair_ids = sorted(p.stem.split("_")[1] for p in settings.testset_dir.glob("rechnung_*.json"))[: args.limit]

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=args.run_name):
        mlflow.log_params({
            "testset_hash": testset_hash(settings.testset_dir), "testset_seed": 42, "n_pairs": len(pair_ids),
            "source": args.source,
            "model": settings.llm_model if args.source == "extraction" else None,
            "prompt_version": PROMPT_VERSION if args.source == "extraction" else None,
            "ocr": settings.ocr_enabled, "matching_threshold": AEHNLICHKEIT_SCHWELLE,
        })
        rows = []
        for i, pair_id in enumerate(pair_ids, 1):
            rows.append(evaluate_pair(pair_id, args.source))
            print(f"[{i}/{len(pair_ids)}] Paar {pair_id}", file=sys.stderr)

        df = pd.DataFrame(rows)
        metrics = summarize_pairs(rows) | {
            "link_accuracy": float(df.link_ok.mean()),
            "error_count": float(df.error.notna().sum()),
        }
        mlflow.log_metrics(metrics)
        mlflow.log_table(df, artifact_file="pair_results.json")

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
