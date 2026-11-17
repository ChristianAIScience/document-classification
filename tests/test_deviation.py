from decimal import Decimal

import pytest

from docclass.pipeline.deviation import find_abweichungen
from docclass.schemas import PositionBase
from evaluation.mapping import abweichung_to_truth_format, from_truth_format
from evaluation.metrics import score_pair, summarize_pairs
from tests.helpers import load_truth

PAIR_IDS = [f"{i:04d}" for i in range(1, 51)]


def detect(pair_id: str) -> list[dict]:
    angebot = from_truth_format(load_truth(f"angebot_{pair_id}"))
    rechnung = from_truth_format(load_truth(f"rechnung_{pair_id}"))
    return [abweichung_to_truth_format(a) for a in find_abweichungen(angebot.positionen, rechnung.positionen)]


@pytest.mark.parametrize("pair_id", PAIR_IDS)
def test_ground_truth_pairs_reproduce_expected_deviations(pair_id):
    """With perfect extraction, the comparison must find exactly the annotated deviation (or none)."""
    expected = load_truth(f"rechnung_{pair_id}")["deviations"]
    found = detect(pair_id)
    assert len(found) == len(expected)
    for f, e in zip(found, expected, strict=True):
        assert (f["type"], f["quote_position"], f["invoice_position"], f["description"]) == (
            e["type"], e["quote_position"], e["invoice_position"], e["description"])
        for key in ("quote_value", "invoice_value"):
            assert (f[key] and Decimal(f[key])) == (e[key] and Decimal(e[key]))


def pos(position: int, beschreibung: str, menge="1", einzelpreis="10.00") -> PositionBase:
    return PositionBase(position=position, beschreibung=beschreibung, menge=menge, einzelpreis=einzelpreis)


def test_noisy_description_is_matched_by_similarity():
    angebot = [pos(1, "Innentürblatt Röhrenspan, CPL weiß, 860 × 1985 mm")]
    rechnung = [pos(1, "Innentürblatt Röhrenspan, CPL weiß,  860 x 1985 mm")]
    assert find_abweichungen(angebot, rechnung) == []


def test_price_and_quantity_change_on_one_item_are_both_reported():
    found = find_abweichungen([pos(1, "Montage", "2", "50.00")], [pos(1, "Montage", "3", "60.00")])
    assert [a.typ for a in found] == ["price_changed", "quantity_changed"]


def test_missing_and_added_items():
    angebot = [pos(1, "Korpus"), pos(2, "Sockelblende"), pos(3, "Montage")]
    rechnung = [pos(1, "Korpus"), pos(2, "Montage"), pos(3, "Anfahrtspauschale")]
    found = [(a.typ, a.angebot_position, a.rechnung_position) for a in find_abweichungen(angebot, rechnung)]
    assert found == [("item_missing", 2, None), ("item_added", None, 3)]


def test_pair_metrics_count_confusion_matrix():
    dev = {"type": "item_added", "quote_position": None, "invoice_position": 4}
    rows = [score_pair([dev], [dev]), score_pair([], []), score_pair([], [dev]), score_pair([dev], [])]
    m = summarize_pairs(rows)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 1)
    assert m["localization_accuracy"] == 0.5


# --- Code review findings #3, #4 --- #

def test_short_similar_descriptions_are_not_merged():
    """#3: 'Montage' vs 'Demontage' are different work items, not OCR noise."""
    found = find_abweichungen([pos(1, "Montage", einzelpreis="60.00")], [pos(1, "Demontage", einzelpreis="70.00")])
    assert [(a.typ, a.angebot_position, a.rechnung_position) for a in found] == [
        ("item_missing", 1, None), ("item_added", None, 1),
    ]


def test_formatting_noise_matches_exactly():
    """Line wraps, hyphenation spaces and '×' vs 'x' do not count as differences."""
    angebot = [pos(1, "Montage der Unter- und Oberschränke vor Ort"), pos(2, "Türblatt 860 × 1985 mm")]
    rechnung = [pos(1, "Montage der Unter-  und Ober schränke vor Ort"), pos(2, "Türblatt 860x1985 mm")]
    assert find_abweichungen(angebot, rechnung) == []


def test_fuzzy_requires_same_unit():
    angebot = [PositionBase(position=1, beschreibung="Innentürblatt Röhrenspan CPL weiß 860 x 1985 mm",
                            menge="1", einheit="Stk.", einzelpreis="10.00")]
    rechnung = [PositionBase(position=1, beschreibung="Innentürblatt Röhrenspan CPL weis 860 x 1985 mm",
                             menge="1", einheit="m²", einzelpreis="10.00")]
    assert [a.typ for a in find_abweichungen(angebot, rechnung)] == ["item_missing", "item_added"]


def test_fuzzy_assignment_is_globally_best_not_first_come():
    """#4: quote pos 1 must not take the invoice item that fits quote pos 2 even better."""
    basis = "Innentürblatt Röhrenspan CPL weiß 860 x 1985 mm"
    angebot = [pos(1, basis), pos(2, basis + " Glas")]
    rechnung = [pos(1, basis + " Glaz"),                                   # OCR noise of quote pos 2
                pos(2, "Innentürbiatt Röhrenspan CPL weis 860 x 1985 rnm")]  # heavy noise of quote pos 1
    assert find_abweichungen(angebot, rechnung) == []
