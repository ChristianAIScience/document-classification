"""Deviation detection between a quote and its invoice (Task B). Deterministic, no LLM.

Positions are matched by description, not by number: after a missing item the invoice is renumbered.
1. Exact match on a compact key (case, whitespace, punctuation and '×'/'x' ignored), which absorbs line wraps
   and hyphenation from PDF extraction.
2. Fuzzy match for leftovers, only when it is safe: long descriptions, same unit, high similarity. Short
   descriptions differ in meaning by a syllable ('Montage' vs 'Demontage'), so they never match fuzzily.
   Fuzzy pairs are assigned best-first over all candidates, not in quote order.
"""

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from docclass.schemas import Abweichung, PositionBase

AEHNLICHKEIT_SCHWELLE = 0.9
MIN_LAENGE_UNSCHARF = 20  # compact characters

_NICHT_ALPHANUM = re.compile(r"[^0-9a-zäöüß]")


def _key(text: str | None) -> str:
    return _NICHT_ALPHANUM.sub("", (text or "").lower().replace("×", "x"))


def _einheit(p: PositionBase) -> str:
    return _key(p.einheit)


def _aehnlichkeit(a: PositionBase, r: PositionBase) -> float:
    ka, kr = _key(a.beschreibung), _key(r.beschreibung)
    if min(len(ka), len(kr)) < MIN_LAENGE_UNSCHARF or _einheit(a) != _einheit(r):
        return 0.0
    return SequenceMatcher(None, ka, kr).ratio()


def match_positionen(
    angebot: Sequence[PositionBase], rechnung: Sequence[PositionBase],
) -> tuple[list[tuple[PositionBase, PositionBase]], list[PositionBase], list[PositionBase]]:
    """Return (matched pairs, quote-only positions, invoice-only positions)."""
    offen = list(rechnung)
    paare: list[tuple[PositionBase, PositionBase]] = []
    ohne_partner: list[PositionBase] = []

    for a in angebot:
        treffer = next((r for r in offen if _key(r.beschreibung) == _key(a.beschreibung)), None)
        if treffer is None:
            ohne_partner.append(a)
        else:
            offen.remove(treffer)
            paare.append((a, treffer))

    kandidaten = sorted(
        ((_aehnlichkeit(a, r), i, j) for i, a in enumerate(ohne_partner) for j, r in enumerate(offen)),
        key=lambda k: k[0], reverse=True,
    )
    vergeben_a: set[int] = set()
    vergeben_r: set[int] = set()
    for score, i, j in kandidaten:
        if score < AEHNLICHKEIT_SCHWELLE:
            break
        if i not in vergeben_a and j not in vergeben_r:
            vergeben_a.add(i)
            vergeben_r.add(j)
            paare.append((ohne_partner[i], offen[j]))

    fehlend = [a for i, a in enumerate(ohne_partner) if i not in vergeben_a]
    hinzugefuegt = [r for j, r in enumerate(offen) if j not in vergeben_r]
    paare.sort(key=lambda p: p[0].position)
    return paare, fehlend, hinzugefuegt


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
