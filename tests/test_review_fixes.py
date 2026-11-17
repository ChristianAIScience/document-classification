"""Regression tests for code review findings #1, #2, #6, #7, #9, #10."""

import pytest

from docclass.db.repository import verknuepfbar
from docclass.pipeline import extraction, service
from evaluation import extraction_cache
from evaluation.mapping import from_truth_format
from evaluation.metrics import score_failed_pair, summarize_pairs
from tests.helpers import FIXTURES, load_truth
from tests.test_api import payload

# --- #1: link check mirrors the DB rules --- #

def test_verknuepfbar_for_real_pair():
    assert verknuepfbar(from_truth_format(load_truth("angebot_0001")), from_truth_format(load_truth("rechnung_0001")))


def test_verknuepfbar_requires_quote_number():
    angebot = from_truth_format(load_truth("angebot_0001")).model_copy(update={"nummer": None})
    rechnung = from_truth_format(load_truth("rechnung_0001")).model_copy(update={"angebot_nummer": None})
    assert not verknuepfbar(angebot, rechnung)  # None == None must not count as a link


def test_verknuepfbar_falls_back_to_company_name():
    angebot = from_truth_format(load_truth("angebot_0001"))
    rechnung = from_truth_format(load_truth("rechnung_0001"))
    rechnung = rechnung.model_copy(update={"lieferant": rechnung.lieferant.model_copy(update={"ust_id": "DE999"})})
    assert verknuepfbar(angebot, rechnung)  # DB matches by name when the VAT ID lookup fails


# --- #2: a failed pair is scored as wrong, never as a true negative --- #

@pytest.mark.parametrize(("truth", "expected"), [
    ([], (0, 1, 0, 0)),                                                      # clean pair → FP
    ([{"type": "item_added", "quote_position": None, "invoice_position": 4}], (0, 0, 1, 0)),  # → FN
])
def test_failed_pair_counts_as_error(truth, expected):
    m = summarize_pairs([score_failed_pair(truth)])
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == expected


# --- #6, #7: extraction cache --- #

@pytest.fixture
def fake_extract(monkeypatch, tmp_path):
    calls = []
    dokument = from_truth_format(load_truth("angebot_0001"))

    def fake(markdown, *, dokumententyp_hint=None):
        calls.append(markdown)
        return dokument

    monkeypatch.setattr(extraction_cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(extraction_cache, "extract", fake)
    return calls


def test_cache_misses_when_system_prompt_changes(fake_extract, monkeypatch):
    extraction_cache.cached_extract("# md")
    extraction_cache.cached_extract("# md")
    assert len(fake_extract) == 1
    monkeypatch.setattr(extraction, "SYSTEM_PROMPT", extraction.SYSTEM_PROMPT + " geändert")
    extraction_cache.cached_extract("# md")
    assert len(fake_extract) == 2


def test_cache_write_is_atomic(fake_extract, monkeypatch, tmp_path):
    def broken_replace(src, dst):
        raise OSError("interrupted")

    monkeypatch.setattr(extraction_cache.os, "replace", broken_replace)
    with pytest.raises(OSError):
        extraction_cache.cached_extract("# md")
    assert not list(tmp_path.glob("*.json"))  # no truncated cache entry left behind


# --- #9: evaluation runs the production pipeline with an injected extractor --- #

def test_process_pdf_uses_injected_extractor(monkeypatch, tmp_path):
    markdown = (FIXTURES / "rechnung_0003.md").read_text(encoding="utf-8")
    monkeypatch.setattr(service, "pdf_to_markdown", lambda path: markdown)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    dokument = from_truth_format(load_truth("rechnung_0003"))

    result = service.process_pdf(pdf, extractor=lambda md, *, dokumententyp_hint=None: dokument)
    assert result.dokument == dokument
    assert result.klassifikation.dokumententyp == "rechnung"
    assert result.warnungen == []


# --- #10: stale links and error message --- #

def test_changing_quote_number_unlinks_invoice(client):
    angebot = client.post("/api/dokumente", json=payload("angebot_0001")).json()
    rechnung = client.post("/api/dokumente", json=payload("rechnung_0001")).json()
    assert rechnung["angebot_id"] == angebot["id"]

    geaendert = payload("angebot_0001") | {"nummer": "AN-ANDERS"}
    assert client.put(f"/api/dokumente/{angebot['id']}", json=geaendert).status_code == 200
    assert client.get(f"/api/dokumente/{rechnung['id']}").json()["angebot_id"] is None


def test_invoice_without_quote_number_has_clear_message(client):
    body = payload("rechnung_0001") | {"angebot_nummer": None}
    rechnung = client.post("/api/dokumente", json=body).json()
    response = client.get(f"/api/dokumente/{rechnung['id']}/abweichungen")
    assert response.status_code == 409
    assert "None" not in response.json()["detail"]
