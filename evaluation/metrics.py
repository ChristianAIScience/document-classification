"""Task A scoring, following .claude/testset-mlflow-guide.md section 3.

`FIELDS` is the guide's field list and defines `exact_match_rate`; `EXTRA_FIELDS` are scored per field only.
"""

from decimal import Decimal

MONEY = {"net", "vat", "gross", "skonto_amount"}
FIELDS = ["doc_type", "number", "issue_date", "due_date", "quote_number",
          "sender.company", "sender.vat_id", "sender.iban", "net", "vat", "gross"]
EXTRA_FIELDS = ["customer_no", "valid_until", "performance_start", "performance_end", "quote_date",
                "subject", "location", "skonto_amount", "sender.street", "sender.postal_code", "sender.city",
                "sender.tax_number", "sender.bic"]


def get(data: dict, path: str):
    for key in path.split("."):
        data = data.get(key) if isinstance(data, dict) else None
    return data


def norm(field: str, value):
    if value is None:
        return None
    if field in MONEY:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    if field == "sender.iban":
        return str(value).replace(" ", "").upper()
    return " ".join(str(value).split())


def score_extraction(truth: dict, pred: dict, fields: list[str] = FIELDS) -> dict[str, bool]:
    return {f: norm(f, get(truth, f)) == norm(f, get(pred, f)) for f in fields}


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def score_items(truth: list[dict], pred: list[dict]) -> dict[str, bool]:
    """Item-level checks: count, totals per position, and full item equality."""
    by_pos = {i["position"]: i for i in pred}

    def same(t: dict, keys: tuple[str, ...]) -> bool:
        p = by_pos.get(t["position"])
        if p is None:
            return False
        return all(
            (" ".join(str(t[k]).split()) == " ".join(str(p.get(k)).split())) if k in ("description", "unit")
            else _dec(t[k]) == _dec(p.get(k))
            for k in keys
        )

    return {
        "items_count": len(truth) == len(pred),
        "items_totals": len(truth) == len(pred) and all(same(t, ("total",)) for t in truth),
        "items_exact": len(truth) == len(pred) and all(
            same(t, ("description", "quantity", "unit", "unit_price", "total")) for t in truth
        ),
    }


# --- Task B: deviation detection per pair (guide section 3, Task B) --- #

DEVIATION_TYPES = ["price_changed", "quantity_changed", "item_missing", "item_added"]


def score_pair(truth: list[dict], pred: list[dict]) -> dict:
    t, p = truth[0] if truth else None, pred[0] if pred else None
    return {
        "actual": bool(t),
        "predicted": bool(p),
        "true_type": t["type"] if t else None,
        "type_ok": bool(t and p and t["type"] == p.get("type")),
        "position_ok": bool(t and p and t["type"] == p.get("type")
                            and (t["quote_position"], t["invoice_position"])
                            == (p.get("quote_position"), p.get("invoice_position"))),
    }


def summarize_pairs(rows: list[dict]) -> dict[str, float]:
    """Binary detection metrics plus type/localization accuracy and recall per type."""
    tp = sum(r["actual"] and r["predicted"] for r in rows)
    fp = sum(not r["actual"] and r["predicted"] for r in rows)
    fn = sum(r["actual"] and not r["predicted"] for r in rows)
    tn = sum(not r["actual"] and not r["predicted"] for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    actual = [r for r in rows if r["actual"]]
    metrics = {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "type_accuracy": sum(r["type_ok"] for r in actual) / len(actual) if actual else 0.0,
        "localization_accuracy": sum(r["position_ok"] for r in actual) / len(actual) if actual else 0.0,
    }
    for typ in DEVIATION_TYPES:
        of_type = [r for r in actual if r["true_type"] == typ]
        if of_type:
            metrics[f"recall_{typ}"] = sum(r["type_ok"] for r in of_type) / len(of_type)
    return {k: float(v) for k, v in metrics.items()}
