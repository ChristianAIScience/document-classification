# Document Classification Agent

## Local setup

1. Install Python 3.12.10 or newer and run `uv sync`.
2. Configure `.env` using `.env.example`, including PostgreSQL connection settings
   (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) and `OPENAI_API_KEY`.
3. Start PostgreSQL and initialize the database explicitly:

   ```powershell
   uv run python src/init_db.py
   ```

   The configured user must be able to connect to the `postgres` database and,
   if the target database does not exist, have permission to create it.
   The command creates missing tables and preserves existing data. It does not
   migrate existing table definitions. Setup errors cause a nonzero exit status.

4. Start the API with `uv run python src/main.py` and open
   `http://127.0.0.1:8000/docs`.

Importing the application does not create the database or tables. Run the
initialization command before serving requests that use the database.

## Database initialization checks

Run `uv run python tests/test_database_initialization.py`.
These checks mock database connections and do not require a running PostgreSQL server.

## Document schemas and models

`ExtractedDokument` in `src/api/schemas.py` describes extraction output without
database IDs. `DokumentCreate` accepts the same nested `kunde` and `positionen`
structure; it does not require a separate top-level `firmen_name`. The current
creation endpoint looks up the customer using `kunde.firmen_name`. If missing,
it creates the customer from the supplied fields. Existing customer details are
preserved. Customer, document, and positions are saved in one transaction.

Document numbers and dates can be omitted or set to `null` for either document
type. Reference numbers are preserved, including an Angebotsnummer on a Rechnung.
Customer name and document type are required. Postal codes and identifiers are
strings. Units accept document-specific text such as `Pauschal`.

Quantities use up to 12 digits with 3 decimal places; unit and total prices use
up to 12 digits with 2 decimal places. Missing values remain `None`.

Existing databases need the new unit-price column before using document endpoints.
Apply this SQL to the configured database (initialization does not alter existing tables):

```sql
ALTER TABLE kunden_dokument_positionen
    ADD COLUMN IF NOT EXISTS einzelpreis NUMERIC(12, 2);
```

Run schema validation and in-memory persistence checks with
`uv run python tests/test_document_schemas.py`.

## API endpoints

Open `/docs` for request bodies and interactive requests.

`src/api/app.py` creates the application and registers the routers. Customer routes
live in `src/api/routers/kunden.py`, document and offer/invoice routes in
`dokumente.py`, and position routes in `dokument_positionen.py`. The HTML home page
has its own `home.py` router. Shared session and lookup helpers are in
`src/api/dependencies.py`, write-conflict handling in `src/api/utils.py`, and shared
document queries in `src/db/queries.py`. Routers do not import each other.

| Method | Path | Purpose |
| --- | --- | --- |
| GET, POST | `/api/kunden` | List or create customers |
| GET, PUT, DELETE | `/api/kunden/{kunde_id}` | Read, replace, or delete a customer |
| GET | `/api/kunden/nr/{kundennummer}` | Find a customer by number |
| GET | `/api/kunden/name/{firmen_name}` | Find a customer by company name |
| GET | `/api/kunden/email/{email}` | Find a customer by email |
| GET | `/api/kunden/{kunde_id}/dokumente` | List a customer's documents |
| GET, POST | `/api/dokumente` | List or create documents |
| GET, PUT, DELETE | `/api/dokumente/{dokument_id}` | Read, replace, or delete a document |
| GET | `/api/dokumente/{dokument_id}/positionen` | Read document positions |
| GET | `/api/angebote` | List offers |
| GET | `/api/angebote/{angebotsnummer}` | List all offers with this number |
| GET | `/api/rechnungen` | List invoices |
| GET | `/api/rechnungen/{rechnungsnummer}` | Read an invoice by number |

`GET /api/dokumente` supports combined exact-match query filters:
`dokumententyp`, `kunde_id`, `angebotsnummer`, `auftragsnummer`, and `rechnungsnummer`.
For example: `/api/dokumente?dokumententyp=rechnung&auftragsnummer=00042`.
List endpoints return `[]` when no documents match; missing individual resources
return `404`.

`PUT` replaces all editable fields, including the complete position list for a
document. Omitted optional values are reset to `null`. Document updates reuse or
create the named customer without overwriting existing customer details; use the
customer endpoint to edit those details. Deleting a document also deletes its
positions and retains the customer. A customer with documents cannot be deleted
(`409`). Successful deletions return `204` with an empty body. Uniqueness conflicts
return `409` and roll back the transaction.

Run HTTP checks against in-memory SQLite with
`uv run python tests/test_api_endpoints.py` (requires the test client dependencies
available in the development environment).

## PostgreSQL vector retrieval

The optional `src/rag/` package provides pgvector storage, text chunking, ingestion,
metadata-filtered similarity search, and a LangChain retriever. Install it with
`uv sync --extra rag`, then initialize explicitly with
`uv run --extra rag python src/init_rag.py` after database setup.
See [the RAG guide](src/rag/README.md) for embedding configuration, usage, and tests.
