from datetime import date
from decimal import Decimal

import pytest

from docclass.pipeline.validation import validate
from docclass.schemas import PositionBase
from evaluation.mapping import from_truth_format, to_truth_format
from evaluation.metrics import EXTRA_FIELDS, FIELDS, score_extraction, score_items
from tests.helpers import all_truths, load_truth


@pytest.mark.parametrize(("raw", "expected"), [
    ("4.297,23", Decimal("4297.23")),
    ("1,5", Decimal("1.5")),
    ("4297.23", Decimal("4297.23")),
    ("1.089,00 €", Decimal("1089.00")),
    (12, Decimal(12)),
])
def test_german_and_iso_numbers_are_parsed(raw, expected):
    assert PositionBase(position=1, gesamtpreis=raw).gesamtpreis == expected


def test_german_dates_are_parsed():
    dokument = from_truth_format(load_truth("rechnung_0003") | {"issue_date": "21.12.2025"})
    assert dokument.datum == date(2025, 12, 21)


@pytest.mark.parametrize("truth", all_truths(), ids=lambda t: t["file"])
def test_ground_truth_passes_validation(truth):
    """Every test set document is arithmetically correct, so validation must not warn."""
    assert validate(from_truth_format(truth)) == []


@pytest.mark.parametrize("truth", all_truths(), ids=lambda t: t["file"])
def test_mapping_roundtrip_scores_perfectly(truth):
    """Ground truth as prediction must score 100 % – guards the mapping and the metrics."""
    pred = to_truth_format(from_truth_format(truth))
    assert all(score_extraction(truth, pred, FIELDS + EXTRA_FIELDS).values())
    assert all(score_items(truth["items"], pred["items"]).values())


def test_validation_detects_wrong_arithmetic():
    truth = load_truth("rechnung_0003")
    truth["gross"] = "1.00"
    truth["items"][0]["total"] = "999.99"
    warnungen = validate(from_truth_format(truth))
    assert any("Position 1" in w for w in warnungen)
    assert any("Summe der Positionen" in w for w in warnungen)
    assert any("Brutto" in w for w in warnungen)


def test_item_scoring_detects_wrong_total():
    truth = load_truth("angebot_0001")
    pred = to_truth_format(from_truth_format(truth))
    pred["items"][0]["total"] = "0.01"
    scores = score_items(truth["items"], pred["items"])
    assert scores["items_count"] and not scores["items_totals"] and not scores["items_exact"]
