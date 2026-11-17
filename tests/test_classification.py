import pytest

from docclass.pipeline.classification import classify
from docclass.pipeline.conversion import strip_watermark
from tests.helpers import FIXTURES


@pytest.mark.parametrize(("fixture", "expected"), [
    ("angebot_0003.md", "angebot"),
    ("rechnung_0003.md", "rechnung"),  # also contains "Angebots-Nr." and "Angebotsdatum"
])
def test_classifies_docling_markdown(fixture, expected):
    result = classify((FIXTURES / fixture).read_text(encoding="utf-8"))
    assert result.dokumententyp == expected
    assert result.konfidenz >= 0.75


def test_footer_words_alone_do_not_decide():
    result = classify("Fiktives Musterdokument – keine echte Rechnung / kein echtes Angebot")
    assert result.dokumententyp is None
    assert result.konfidenz == 0.0


def test_strip_watermark_keeps_words_inside_text():
    assert strip_watermark("Zeile\nMUSTER\nMUSTERAI GmbH") == "Zeile\n\nMUSTERAI GmbH"
