# Project-A - Private Servers

Project-A is a local server reconstruction for the early Project A / Valorant client. It provides a Python implementation of the client-facing HTTP/RNet control plane, a lightweight game-port observer/responder, launch scripts for local testing, and tests for the recovered API surface.

The goal is research, preservation, and protocol documentation for the original Project A experience. The repository contains source code and tooling only. Game binaries, dumps, IDA databases, generated SDKs, runtime logs, certificates, and other local artifacts are intentionally ignored and should not be committed.

## Current Status

This project is still experimental. The local control plane is functional enough for client bootstrap, auth/config, chat/session, party, matchmaking, pregame/core-game payloads, store/entitlements, contracts, loadout, and related smoke coverage. The gameplay side is not a full Unreal dedicated server yet; it is currently a local observer/stateless responder for the recovered game socket path.

Known limitations:

- Gameplay simulation is incomplete.
- Some protocol details are still inferred from client behavior.
- Client launch mutates local certificate bundles so the old client trusts the generated local TLS certificate.
- PostgreSQL persistence is supported, but the zero-config launcher uses in-memory storage when no database URL is configured.

## Requirements

- Windows for the bundled batch/PowerShell launch flow.
- Python 3.12 or newer.
- A local Project A client folder named `Project A Valorant` beside this repository when using `start_client.bat`.
- PostgreSQL is optional for durable account/state storage.

Recommended PostgreSQL defaults:

```text
Database: projecta
Username: projecta
Password: projecta
URL: postgresql://projecta:projecta@127.0.0.1:5432/projecta
```

## Repository Layout

Keep the repository next to the extracted local client folder:

```text
project A/
  Server/
  scripts/
  tests/
  tools/
  start_server.bat
  start_client.bat
  Project A Valorant/        local client folder, ignored by git
  DUMP/                      local reversing artifacts, ignored by git
```

Do not merge the repository files into the game directory. The launchers expect the game folder to sit beside the repository files.

## Quick Start

Start only the local server:

```bat
start_server.bat
```

For scripted runs that should not pause at the end, set `PROJECT_A_NO_PAUSE=1` before calling either batch file.

This creates `.venv`, installs dependencies from `requirements.txt`, and starts the local control-plane server on:

```text
http://127.0.0.1:39001
```

If neither `PROJECTA_DATABASE_URL`, `DATABASE_URL`, nor `--database-url` is set, `start_server.bat` adds `--allow-memory-db` automatically for a zero-config local run. If a database URL is configured, PostgreSQL is used instead.

## Launching The Client

Start the local server stack and open the game:

```bat
start_client.bat
```

`start_client.bat` asks for a Riot ID in `GameName#TAG` format, defaulting to `DevPlayer#LOCAL` when left blank. It uses this executable automatically:

```text
Project A Valorant\ShooterClient.exe
```

To use a different client executable:

```powershell
.\start_client.bat -ClientExe "C:\Path\To\ShooterClient.exe"
```

The client launcher patches only the local `Project A Valorant` certificate bundles so the client trusts the generated local server certificate. If the client folder does not contain `cacert.pem` files yet, the launcher creates the expected bundle paths automatically. Backups for existing files are written as `*.bak-local-ca`, and both the client folder and backups are ignored by git.

The lower-level PowerShell launcher is available for scripted runs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_client.ps1 -ClientExe "Project A Valorant\ShooterClient.exe" -RiotName "DevPlayer#LOCAL" -PatchClientCerts
```

## Manual Server Start

Check launcher options:

```powershell
.\start_server.bat --help
```

Or, if you prefer to manage Python yourself:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python Server\project_a_server.py --host 127.0.0.1 --port 39001 --allow-memory-db --reset-state
```

Use PostgreSQL manually:

```powershell
$env:PROJECTA_DATABASE_URL = "postgresql://projecta:projecta@127.0.0.1:5432/projecta"
python Server\project_a_server.py --host 127.0.0.1 --port 39001 --database-url $env:PROJECTA_DATABASE_URL
```

## Docker

Docker Compose starts PostgreSQL and the server together:

```bash
docker compose up --build
```

The containerized server listens on port `39001` and connects to PostgreSQL through the Compose service name `postgres`.

## Testing

Install dev dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run pytest:

```powershell
python -m pytest
```

Run the standalone HTTP smoke scripts when changing route behavior:

```powershell
python tests\run_smoke.py
python tests\test_http_contract.py
python tests\test_http_contracts.py
python tests\test_endpoint_matrix.py
python tests\test_full_api_surface.py
```

## Features

- Local HTTP/HTTPS RNet-compatible control plane.
- Same-port HTTP and HTTPS handling for recovered client paths.
- Local account creation, alias handling, auth token, entitlement token, and Riot-style display names.
- Party, matchmaking, pregame, core-game, chat, voice, session, content, contracts, store, wallet, and entitlement route families.
- In-memory storage for disposable runs and PostgreSQL storage for durable local state.
- Local game-port observer/stateless responder for the recovered UDP/TCP game socket path.
- Docker Compose stack for PostgreSQL-backed server testing.
- Pytest and standalone smoke coverage for the API surface.

## Code Layout

```text
Server/project_a_server.py              server compatibility entry point
Server/app.py                           compatibility wrapper for old imports
Server/accounts.py                      compatibility wrapper for old imports
Server/game_socket.py                   gameplay observer wrapper
Server/ue_game_server.py                UE-style gameplay responder entry point
Server/projecta/control_plane/app.py    public facade used by routes and tests
Server/projecta/control_plane/server.py CLI bootstrap
Server/projecta/control_plane/common/   shared helpers
Server/projecta/control_plane/data/     static catalog and content type data
Server/projecta/control_plane/domain/   account, queue, and state logic
Server/projecta/control_plane/payloads/ response builders by API family
Server/projecta/control_plane/routes/   modular HTTP route handlers
Server/projecta/control_plane/runtime/  HTTP/WebSocket runtime and dispatch
Server/projecta/gameplay/               game-port observer/responder modules
Server/projecta/storage/                memory/PostgreSQL account store and SQL schema
scripts/launch_client.ps1               lower-level client/server launcher
tools/manage_accounts.py                PostgreSQL account management helper
tests/                                  unit and smoke tests
```

## Environment Variables

The launchers read process environment variables from the current shell. They do not automatically load `.env` files.

Useful variables:

```text
PROJECTA_DATABASE_URL=postgresql://projecta:projecta@127.0.0.1:5432/projecta
DATABASE_URL=postgresql://projecta:projecta@127.0.0.1:5432/projecta
PROJECT_A_RIOT_ID=DevPlayer#LOCAL
PROJECT_A_CLIENT_EXE=C:\Path\To\ShooterClient.exe
PROJECT_A_AUTO_ACCEPT_FRIEND_REQUESTS=0
PROJECT_A_ALLOW_UNVERIFIED_DEFAULT_LOADOUT=0
```

## Repo Hygiene

`.gitignore` and `.dockerignore` exclude generated and local-only artifacts, including:

- `.venv*/`, `__pycache__/`, `.pytest_cache/`, coverage and build output.
- `reverse-logs/`, `*.log`, `*.jsonl`, generated `*.crt`, `*.key`, and `*.pem` files.
- `Project A Valorant/`, `DUMP/`, generated SDK output, IDA databases, executables, DLLs, PAK files, dumps, and certificate backups.

If you initialize git from this directory, these local artifacts should remain untracked unless force-added.

## Contributing

Useful contributions include route fixes, protocol notes, payload shape evidence, tests, storage improvements, and gameplay handoff research. Keep committed changes limited to source code, tests, documentation, and safe tooling. Do not commit game binaries, generated dumps, private logs, local certificates, or secrets.

## Disclaimer

This project is intended for research, education, and preservation. It is not affiliated with or endorsed by Riot Games. All rights to Valorant, Project A, and related assets belong to Riot Games.

## License

No license has been selected yet. Treat the code as all-rights-reserved unless a license is added later.
