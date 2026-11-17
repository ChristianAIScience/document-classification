from docclass.pipeline import service
from docclass.pipeline.classification import Klassifikation
from evaluation.mapping import from_truth_format
from tests.helpers import TESTSET, load_truth


def payload(name: str) -> dict:
    return from_truth_format(load_truth(name)).model_dump(mode="json")


def test_create_rechnung_then_angebot_links_both_ways(client):
    rechnung = client.post("/api/dokumente", json=payload("rechnung_0003"))
    assert rechnung.status_code == 201, rechnung.text
    assert rechnung.json()["angebot_id"] is None

    angebot = client.post("/api/dokumente", json=payload("angebot_0003"))
    assert angebot.status_code == 201
    # Same supplier is reused (matched via USt-ID) and the earlier invoice now points to the quote.
    assert angebot.json()["lieferant_id"] == rechnung.json()["lieferant_id"]
    linked = client.get(f"/api/dokumente/{rechnung.json()['id']}").json()
    assert linked["angebot_id"] == angebot.json()["id"]


def test_create_angebot_then_rechnung_links(client):
    angebot = client.post("/api/dokumente", json=payload("angebot_0001")).json()
    rechnung = client.post("/api/dokumente", json=payload("rechnung_0001")).json()
    assert rechnung["angebot_id"] == angebot["id"]
    assert rechnung["netto"] == load_truth("rechnung_0001")["net"]
    assert len(rechnung["positionen"]) == len(load_truth("rechnung_0001")["items"])


def test_same_number_same_supplier_conflicts(client):
    assert client.post("/api/dokumente", json=payload("angebot_0001")).status_code == 201
    assert client.post("/api/dokumente", json=payload("angebot_0001")).status_code == 409


def test_filters_and_shortcuts(client):
    for name in ("angebot_0001", "rechnung_0001", "angebot_0002"):
        client.post("/api/dokumente", json=payload(name))
    assert len(client.get("/api/angebote").json()) == 2
    assert len(client.get("/api/rechnungen").json()) == 1
    nummer = load_truth("rechnung_0001")["number"]
    assert [d["nummer"] for d in client.get(f"/api/rechnungen/{nummer}").json()] == [nummer]
    quote = load_truth("rechnung_0001")["quote_number"]
    assert len(client.get("/api/dokumente", params={"angebot_nummer": quote}).json()) == 1
    assert client.get("/api/dokumente", params={"dokumententyp": "rechnung", "nummer": "gibt-es-nicht"}).json() == []


def test_put_replaces_positions_and_delete_cascades(client):
    created = client.post("/api/dokumente", json=payload("angebot_0001")).json()
    body = payload("angebot_0001")
    body["positionen"] = body["positionen"][:1]
    updated = client.put(f"/api/dokumente/{created['id']}", json=body)
    assert updated.status_code == 200
    assert len(client.get(f"/api/dokumente/{created['id']}/positionen").json()) == 1

    lieferant_id = created["lieferant_id"]
    assert client.delete(f"/api/lieferanten/{lieferant_id}").status_code == 409
    assert client.delete(f"/api/dokumente/{created['id']}").status_code == 204
    assert client.get(f"/api/dokumente/{created['id']}").status_code == 404
    assert client.delete(f"/api/lieferanten/{lieferant_id}").status_code == 204


def test_lieferanten_crud(client):
    body = {"firmenname": "Holzbau Test", "ust_id": "DE111111111"}
    created = client.post("/api/lieferanten", json=body)
    assert created.status_code == 201
    assert client.post("/api/lieferanten", json=body).status_code == 409
    assert client.get("/api/lieferanten", params={"ust_id": "DE111111111"}).json()[0]["firmenname"] == "Holzbau Test"
    assert client.get("/api/lieferanten/999").status_code == 404


def test_invalid_dokumententyp_rejected(client):
    body = payload("angebot_0001") | {"dokumententyp": "lieferschein"}
    assert client.post("/api/dokumente", json=body).status_code == 422


def _fake_process(pdf_name: str):
    def fake(path, *, quelldatei=None):
        dokument = from_truth_format(load_truth(pdf_name))
        return service.ProcessingResult(
            quelldatei=quelldatei, datei_hash=service.sha256_file(path), markdown="# md",
            klassifikation=Klassifikation(dokument.dokumententyp, 1.0, {}), dokument=dokument, warnungen=[],
        )
    return fake


def test_upload_stores_document_and_rejects_duplicates(client, monkeypatch, tmp_path):
    monkeypatch.setattr(service, "process_pdf", _fake_process("angebot_0001"))
    monkeypatch.setattr("docclass.core.config.settings.uploads_dir", tmp_path)
    pdf = (TESTSET / "angebot_0001.pdf").read_bytes()

    first = client.post("/api/dokumente/upload", files={"datei": ("angebot_0001.pdf", pdf, "application/pdf")})
    assert first.status_code == 201, first.text
    assert first.json()["quelldatei"] == "angebot_0001.pdf"
    assert first.json()["prompt_version"] is not None

    second = client.post("/api/dokumente/upload", files={"datei": ("kopie.pdf", pdf, "application/pdf")})
    assert second.status_code == 409


def test_upload_rejects_non_pdf(client):
    response = client.post("/api/dokumente/upload", files={"datei": ("x.txt", b"hello", "text/plain")})
    assert response.status_code == 415
