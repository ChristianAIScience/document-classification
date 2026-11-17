"""Deviation detection between a quote and its invoice (Task B). Deterministic, no LLM.

Positions are matched by description, not by number: after a missing item the invoice is renumbered.
Exact (whitespace- and case-normalized) matches come first; leftovers are paired by similarity, so OCR or
extraction noise in a description does not turn into a missing/added pair.
"""

from collections.abc import Sequence
from difflib import SequenceMatcher

from docclass.schemas import Abweichung, PositionBase

AEHNLICHKEIT_SCHWELLE = 0.85


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def match_positionen(
    angebot: Sequence[PositionBase], rechnung: Sequence[PositionBase],
) -> tuple[list[tuple[PositionBase, PositionBase]], list[PositionBase], list[PositionBase]]:
    """Return (matched pairs, quote-only positions, invoice-only positions), each in position order."""
    offen = list(rechnung)
    paare: list[tuple[PositionBase, PositionBase]] = []
    ohne_partner: list[PositionBase] = []

    for a in angebot:
        treffer = next((r for r in offen if _norm(r.beschreibung) == _norm(a.beschreibung)), None)
        if treffer is None:
            ohne_partner.append(a)
        else:
            offen.remove(treffer)
            paare.append((a, treffer))

    fehlend: list[PositionBase] = []
    for a in ohne_partner:
        bewertet = [(SequenceMatcher(None, _norm(a.beschreibung), _norm(r.beschreibung)).ratio(), r) for r in offen]
        score, treffer = max(bewertet, key=lambda x: x[0], default=(0.0, None))
        if treffer is not None and score >= AEHNLICHKEIT_SCHWELLE:
            offen.remove(treffer)
            paare.append((a, treffer))
        else:
            fehlend.append(a)

    paare.sort(key=lambda p: p[0].position)
    return paare, fehlend, offen


def find_abweichungen(angebot: Sequence[PositionBase], rechnung: Sequence[PositionBase]) -> list[Abweichung]:
    """All deviations, ordered by quote position (added items by invoice position at the end)."""
    paare, fehlend, hinzugefuegt = match_positionen(angebot, rechnung)
    abweichungen: list[Abweichung] = []

    for a, r in paare:
        for typ, alt, neu in (
            ("price_changed", a.einzelpreis, r.einzelpreis),
            ("quantity_changed", a.menge, r.menge),
        ):
            if alt is not None and neu is not None and alt != neu:
                abweichungen.append(Abweichung(
                    typ=typ, angebot_position=a.position, rechnung_position=r.position,
                    beschreibung=a.beschreibung, angebot_wert=alt, rechnung_wert=neu,
                ))
    abweichungen += [
        Abweichung(typ="item_missing", angebot_position=a.position, rechnung_position=None, beschreibung=a.beschreibung)
        for a in fehlend
    ]
    abweichungen.sort(key=lambda x: x.angebot_position)
    abweichungen += [
        Abweichung(typ="item_added", angebot_position=None, rechnung_position=r.position, beschreibung=r.beschreibung)
        for r in sorted(hinzugefuegt, key=lambda r: r.position)
    ]
    return abweichungen
