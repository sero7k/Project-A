# Project A Server

Local service emulator for the abandoned Project A client. This repository intentionally contains only server source, schema, tests, and helper scripts. Client binaries, dumps, reverse logs, and generated certificates are not part of this server artifact.

## Requirements

- Python 3.12+
- PostgreSQL
- Python dependencies from `requirements.txt`

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a PostgreSQL database/user that matches `.env.example`, or set `PROJECTA_DATABASE_URL` / `DATABASE_URL` to your own connection string. The server applies `sql/schema.sql` on startup unless `--no-db-migrate` is passed.

## Run

```powershell
python .\project_a_server.py --database-url "postgresql://projecta:projecta@127.0.0.1:5432/projecta"
```

For local smoke tests without PostgreSQL:

```powershell
python .\project_a_server.py --allow-memory-db
```

The in-memory mode is only for development checks. Normal startup uses PostgreSQL so accounts, display names, and party membership are persisted.

## Accounts And Parties

Accounts are created on first use from the remoting auth token. The account table stores the local account key, subject UUID, game name, and tag line.

Each account receives a distinct default party. Observing a second account no longer adds it to the current player’s lobby. A second player appears in the same party only after an explicit party join route is handled.

## Tests

```powershell
python -m pytest
```

The test suite covers account creation, distinct default parties, party chat participant isolation, explicit party joining, and an HTTP smoke test against a running local server instance.
