"""Translate between ground-truth JSON (see .claude/testset-mlflow-guide.md) and `ExtractedDokument`."""

from docclass.schemas import ExtractedDokument


def to_truth_format(d: ExtractedDokument) -> dict:
    """Prediction in the key layout of the test set JSON, so the guide's scoring applies unchanged."""
    s = lambda v: None if v is None else str(v)
    lf = d.lieferant
    return {
        "doc_type": d.dokumententyp,
        "number": d.nummer,
        "issue_date": s(d.datum),
        "customer_no": d.kundennummer,
        "valid_until": s(d.gueltig_bis),
        "performance_start": s(d.leistung_beginn),
        "performance_end": s(d.leistung_ende),
        "due_date": s(d.faellig_am),
        "quote_number": d.angebot_nummer,
        "quote_date": s(d.angebot_datum),
        "sender": {
            "company": lf.firmenname, "street": lf.strasse, "postal_code": lf.plz, "city": lf.ort,
            "tax_number": lf.steuernummer, "vat_id": lf.ust_id, "iban": lf.iban, "bic": lf.bic,
        },
        "subject": d.betreff,
        "location": d.leistungsort,
        "items": [
            {"position": p.position, "description": p.beschreibung, "quantity": s(p.menge), "unit": p.einheit,
             "unit_price": s(p.einzelpreis), "total": s(p.gesamtpreis)}
            for p in d.positionen
        ],
        "net": s(d.netto), "vat": s(d.mwst), "gross": s(d.brutto), "skonto_amount": s(d.skonto_betrag),
    }


def from_truth_format(t: dict) -> ExtractedDokument:
    """Ground truth as `ExtractedDokument` (used by tests to check validation and mapping)."""
    sender = t["sender"]
    return ExtractedDokument(
        dokumententyp=t["doc_type"], nummer=t["number"], datum=t["issue_date"], kundennummer=t["customer_no"],
        gueltig_bis=t["valid_until"], leistung_beginn=t["performance_start"], leistung_ende=t["performance_end"],
        faellig_am=t["due_date"], angebot_nummer=t["quote_number"], angebot_datum=t["quote_date"],
        betreff=t["subject"], leistungsort=t["location"],
        netto=t["net"], mwst=t["vat"], brutto=t["gross"], skonto_betrag=t["skonto_amount"],
        lieferant={
            "firmenname": sender["company"], "strasse": sender["street"], "plz": sender["postal_code"],
            "ort": sender["city"], "steuernummer": sender["tax_number"], "ust_id": sender["vat_id"],
            "iban": sender["iban"], "bic": sender["bic"],
        },
        positionen=[
            {"position": i["position"], "beschreibung": i["description"], "menge": i["quantity"],
             "einheit": i["unit"], "einzelpreis": i["unit_price"], "gesamtpreis": i["total"]}
            for i in t["items"]
        ],
    )
