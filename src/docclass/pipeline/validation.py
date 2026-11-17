"""Deterministic plausibility checks on extracted documents. Returns warnings, never raises."""

from decimal import ROUND_HALF_UP, Decimal

from docclass.schemas import DokumentBase

CENT = Decimal("0.01")
MWST_SATZ = Decimal("0.19")


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def validate(dokument: DokumentBase) -> list[str]:
    warnungen: list[str] = []

    for feld in ("nummer", "datum", "netto", "brutto"):
        if getattr(dokument, feld) is None:
            warnungen.append(f"Pflichtfeld fehlt: {feld}")

    for p in dokument.positionen:
        if None not in (p.menge, p.einzelpreis, p.gesamtpreis) and _round(p.menge * p.einzelpreis) != p.gesamtpreis:
            warnungen.append(
                f"Position {p.position}: {p.menge} × {p.einzelpreis} ≠ {p.gesamtpreis}"
            )

    summen = [p.gesamtpreis for p in dokument.positionen]
    if dokument.netto is not None and summen and None not in summen and sum(summen) != dokument.netto:
        warnungen.append(f"Summe der Positionen {sum(summen)} ≠ Netto {dokument.netto}")

    if dokument.netto is not None and dokument.mwst is not None:
        if _round(dokument.netto * MWST_SATZ) != dokument.mwst:
            warnungen.append(f"MwSt {dokument.mwst} ≠ 19 % von {dokument.netto}")
        if dokument.brutto is not None and dokument.netto + dokument.mwst != dokument.brutto:
            warnungen.append(f"Netto + MwSt ≠ Brutto {dokument.brutto}")

    return warnungen
