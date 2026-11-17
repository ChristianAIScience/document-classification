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
