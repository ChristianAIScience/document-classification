import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTSET = ROOT / "data" / "testset"
FIXTURES = Path(__file__).parent / "fixtures"


def load_truth(name: str) -> dict:
    return json.loads((TESTSET / f"{name}.json").read_text(encoding="utf-8"))


def all_truths() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TESTSET.glob("*.json"))]
