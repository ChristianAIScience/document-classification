# Document Classification Agent

Liest eingehende **Angebote und Rechnungen** (PDF), konvertiert sie mit **Docling** (inkl. OCR) zu Markdown,
klassifiziert sie, extrahiert alle Felder und speichert sie in **PostgreSQL**.

```
PDF ──Docling──▶ Markdown ──Regeln──▶ Typ (angebot/rechnung)
                    │                      │ (Hinweis)
                    └──────LLM (structured output)──▶ ExtractedDokument ──Validierung──▶ PostgreSQL
```

| Schritt | Modul | Bemerkung |
| --- | --- | --- |
| Konvertierung | `src/docclass/pipeline/conversion.py` | Docling, pypdfium2-Backend, Kopf/Fußzeile inklusive (IBAN, USt-ID), Cache in `data/markdown_cache/` |
| Klassifikation | `pipeline/classification.py` | regelbasiert mit Konfidenz; ab 0,75 gewinnt sie gegen das LLM |
| Extraktion | `pipeline/extraction.py` | LangChain `ChatOpenAI.with_structured_output(ExtractedDokument)`, `PROMPT_VERSION` |
| Validierung | `pipeline/validation.py` | Decimal-Arithmetik: Positionen, Netto, 19 % MwSt, Brutto → Warnungen |
| Orchestrierung | `pipeline/service.py` | `process_pdf(path)` ohne DB-Zugriff |

## Setup

1. Python ≥ 3.12.10, dann `uv sync --all-groups`.
2. `.env` aus `.env.example` anlegen (PostgreSQL-Zugang, `OPENAI_API_KEY`; optional `LLM_MODEL`, `OCR_ENABLED`).
3. Datenbank anlegen und Schema migrieren:

   ```powershell
   uv run python -m docclass.db.create_database   # CREATE DATABASE, falls nicht vorhanden
   uv run alembic upgrade head
   ```

4. API starten: `uv run python -m uvicorn docclass.api.app:app --reload` → <http://127.0.0.1:8000/docs>

### Hinweis Windows / Smart App Control

Die Anwendungssteuerung blockiert hier native DLLs von `docling-parse` und `pyarrow`. Deshalb nutzt die
Konvertierung das pypdfium2-Backend, und die Evaluation verwendet `mlflow-skinny` (ohne pyarrow). Kein Paket
installieren, das `pyarrow` mitbringt (z. B. Voll-`mlflow`): pandas lädt es sonst, und Docling bricht beim Import.

## Datenmodell

`lieferanten` (Absender: Firma, Adresse, Steuernr., USt-ID, IBAN, BIC) → `dokumente` (Typ, Nummer, Daten,
Beträge, Angebotsreferenz, Herkunft: Datei-Hash, Markdown, Modell, Prompt-Version, Warnungen) →
`dokument_positionen`.

- Lieferanten werden über die USt-ID, sonst über den Firmennamen zugeordnet.
- Eindeutig: `(lieferant_id, dokumententyp, nummer)` und `datei_hash` (Upload ist idempotent).
- Rechnungen werden über `angebot_nummer` mit dem Angebot desselben Lieferanten verknüpft (`angebot_id`),
  unabhängig von der Upload-Reihenfolge.
- Jede Schemaänderung: Modell anpassen → `uv run alembic revision --autogenerate -m "..."` → Migration prüfen →
  `uv run alembic upgrade head`. Alembic verwaltet nur Tabellen aus `docclass.db.models`; fremde Tabellen bleiben unberührt.

## API

| Methode | Pfad | Zweck |
| --- | --- | --- |
| POST | `/api/dokumente/upload` | PDF hochladen → Pipeline → speichern (409 bei gleicher Datei) |
| GET, POST | `/api/dokumente` | Liste (Filter: `dokumententyp`, `lieferant_id`, `nummer`, `angebot_nummer`) / manuell anlegen |
| GET, PUT, DELETE | `/api/dokumente/{id}` | Lesen, ersetzen (inkl. aller Positionen), löschen |
| GET | `/api/dokumente/{id}/positionen` | Positionen |
| GET | `/api/angebote`, `/api/angebote/{nummer}` | Angebote |
| GET | `/api/rechnungen`, `/api/rechnungen/{nummer}` | Rechnungen (Nummern sind nur je Lieferant eindeutig → Liste) |
| GET, POST | `/api/lieferanten` | Liste (Filter `firmenname`, `ust_id`) / anlegen |
| GET, PUT, DELETE | `/api/lieferanten/{id}` | Lesen, ersetzen, löschen (409 solange Dokumente existieren) |
| GET | `/api/lieferanten/{id}/dokumente` | Dokumente eines Lieferanten |

## CLI

```powershell
uv run docclass process data/testset/rechnung_0001.pdf          # JSON-Ausgabe
uv run docclass process data/testset --save                      # ganzer Ordner, in PostgreSQL speichern
```

## Tests

`uv run pytest` – ohne Netzwerk, LLM und PostgreSQL (SQLite in-memory, Markdown-Fixtures in `tests/fixtures/`).

## Evaluation (Task A: Extraktion)

Testset: `data/testset/` (50 Paare, eingefroren, siehe `.claude/testset-mlflow-guide.md`).

Vorher den MLflow-Tracking-Server starten (Docker Desktop muss laufen):

```powershell
docker compose up -d mlflow      # UI: http://localhost:5000, Daten in ./mlflow-data
docker compose down              # stoppen (Daten bleiben erhalten)
```

```powershell
uv run --group eval python -m evaluation.run_extraction --run-name <name>              # volle Pipeline
uv run --group eval python -m evaluation.run_extraction --classification-only          # nur Regeln, ohne LLM
uv run --group eval python -m evaluation.run_extraction --limit 5                      # Smoke-Test
```

Geloggt werden `testset_hash`, Modell, Prompt-Version, OCR sowie `acc_<feld>`, `exact_match_rate`
(Guide-Felder), `doc_type_accuracy`, `items_*_accuracy`, `validation_pass_rate` und eine Tabelle pro Dokument.
Ziel ist `MLFLOW_TRACKING_URI` (Standard `http://localhost:5000`); Artefakte gehen per HTTP an den Server
(`--serve-artifacts`). Die MLflow-UI läuft nur im Container, weil Smart App Control die lokale Installation blockiert.
