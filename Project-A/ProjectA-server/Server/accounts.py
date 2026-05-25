from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DATABASE_URL = "postgresql://projecta:projecta@127.0.0.1:5432/projecta"
ACCOUNT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project-a-local-account")
PARTY_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project-a-local-party")


@dataclass(frozen=True)
class AccountRecord:
    account_key: str
    subject: str
    game_name: str
    tag_line: str

    @property
    def display_name(self) -> str:
        return f"{self.game_name}#{self.tag_line}"


def normalize_account_key(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    key = re.sub(r"[^a-z0-9_-]+", "", key)
    return key or "developer"


def generated_subject(account_key: str) -> str:
    return str(uuid.uuid5(ACCOUNT_NAMESPACE, account_key))


def generated_party_id(subject: str) -> str:
    return str(uuid.uuid5(PARTY_NAMESPACE, subject.lower()))


def generated_name(account_key: str) -> tuple[str, str]:
    suffix_match = re.search(r"(\d+)$", account_key)
    suffix = suffix_match.group(1) if suffix_match else generated_subject(account_key)[:4].upper()
    return f"DevPlayer{suffix}", f"LOCAL{suffix}"


def account_from_hint(account_key: str, hint: dict[str, str] | None = None) -> AccountRecord:
    hint = hint or {}
    game_name, tag_line = generated_name(account_key)
    return AccountRecord(
        account_key=account_key,
        subject=str(hint.get("subject") or generated_subject(account_key)),
        game_name=str(hint.get("game_name") or game_name),
        tag_line=str(hint.get("tag_line") or tag_line),
    )


class MemoryAccountStore:
    """Test/local fallback with the same semantics as the PostgreSQL store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._accounts: dict[str, AccountRecord] = {}
        self._party_owner: dict[str, str] = {}
        self._member_party: dict[str, str] = {}

    def migrate(self) -> None:
        return

    def get_or_create_account(self, account_key: str, hint: dict[str, str] | None = None) -> AccountRecord:
        account_key = normalize_account_key(account_key)
        with self._lock:
            account = self._accounts.get(account_key)
            if not account:
                account = account_from_hint(account_key, hint)
                self._accounts[account_key] = account
            self.ensure_default_party(account)
            return account

    def get_account_by_subject(self, subject: str) -> AccountRecord | None:
        subject = str(subject or "").lower()
        with self._lock:
            for account in self._accounts.values():
                if account.subject.lower() == subject:
                    return account
        return None

    def ensure_default_party(self, account: AccountRecord) -> str:
        party_id = generated_party_id(account.subject)
        with self._lock:
            self._party_owner.setdefault(party_id, account.account_key)
            self._member_party.setdefault(account.account_key, party_id)
        return party_id

    def current_party_id(self, account_key: str) -> str:
        account = self.get_or_create_account(account_key)
        with self._lock:
            return self._member_party.get(account.account_key) or self.ensure_default_party(account)

    def join_party(self, account_key: str, party_id: str) -> None:
        account = self.get_or_create_account(account_key)
        with self._lock:
            self._party_owner.setdefault(party_id, account.account_key)
            self._member_party[account.account_key] = party_id

    def leave_party(self, account_key: str) -> str:
        account = self.get_or_create_account(account_key)
        with self._lock:
            self._member_party.pop(account.account_key, None)
        return self.ensure_default_party(account)

    def party_members(self, party_id: str) -> list[AccountRecord]:
        with self._lock:
            keys = [key for key, current_party in self._member_party.items() if current_party == party_id]
            return [self._accounts[key] for key in sorted(keys) if key in self._accounts]

    def known_accounts(self) -> list[AccountRecord]:
        with self._lock:
            return [self._accounts[key] for key in sorted(self._accounts)]


class PostgresAccountStore:
    def __init__(self, database_url: str, schema_path: Path | None = None) -> None:
        self.database_url = database_url
        self.schema_path = schema_path or Path(__file__).with_name("sql").joinpath("schema.sql")

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL account storage. "
                "Install Server/requirements.txt or run with --allow-memory-db for local tests."
            ) from exc
        return psycopg.connect(self.database_url)

    def migrate(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            for statement in schema.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)

    def get_or_create_account(self, account_key: str, hint: dict[str, str] | None = None) -> AccountRecord:
        account = account_from_hint(normalize_account_key(account_key), hint)
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO accounts (account_key, subject, game_name, tag_line)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (account_key) DO UPDATE SET updated_at = now()
                RETURNING account_key, subject::text, game_name, tag_line
                """,
                (account.account_key, account.subject, account.game_name, account.tag_line),
            ).fetchone()
            stored = AccountRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]))
            conn.commit()
            self.ensure_default_party(stored)
            return stored

    def get_account_by_subject(self, subject: str) -> AccountRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT account_key, subject::text, game_name, tag_line
                FROM accounts
                WHERE subject = %s
                """,
                (str(subject),),
            ).fetchone()
        if not row:
            return None
        return AccountRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]))

    def ensure_default_party(self, account: AccountRecord) -> str:
        party_id = generated_party_id(account.subject)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parties (id, owner_account_key)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (party_id, account.account_key),
            )
            conn.execute(
                """
                INSERT INTO party_members (account_key, party_id)
                VALUES (%s, %s)
                ON CONFLICT (account_key) DO NOTHING
                """,
                (account.account_key, party_id),
            )
        return party_id

    def current_party_id(self, account_key: str) -> str:
        account = self.get_or_create_account(account_key)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT party_id::text FROM party_members WHERE account_key = %s",
                (account.account_key,),
            ).fetchone()
        if row:
            return str(row[0])
        return self.ensure_default_party(account)

    def join_party(self, account_key: str, party_id: str) -> None:
        account = self.get_or_create_account(account_key)
        party_uuid = str(uuid.UUID(str(party_id)))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parties (id, owner_account_key)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (party_uuid, account.account_key),
            )
            conn.execute(
                """
                INSERT INTO party_members (account_key, party_id)
                VALUES (%s, %s)
                ON CONFLICT (account_key) DO UPDATE SET party_id = EXCLUDED.party_id, joined_at = now()
                """,
                (account.account_key, party_uuid),
            )

    def leave_party(self, account_key: str) -> str:
        account = self.get_or_create_account(account_key)
        default_party = generated_party_id(account.subject)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parties (id, owner_account_key)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (default_party, account.account_key),
            )
            conn.execute(
                """
                INSERT INTO party_members (account_key, party_id)
                VALUES (%s, %s)
                ON CONFLICT (account_key) DO UPDATE SET party_id = EXCLUDED.party_id, joined_at = now()
                """,
                (account.account_key, default_party),
            )
        return default_party

    def party_members(self, party_id: str) -> list[AccountRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.account_key, a.subject::text, a.game_name, a.tag_line
                FROM accounts a
                JOIN party_members pm ON pm.account_key = a.account_key
                WHERE pm.party_id = %s
                ORDER BY pm.joined_at, a.account_key
                """,
                (str(uuid.UUID(str(party_id))),),
            ).fetchall()
        return [AccountRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows]

    def known_accounts(self) -> list[AccountRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT account_key, subject::text, game_name, tag_line
                FROM accounts
                ORDER BY account_key
                """
            ).fetchall()
        return [AccountRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows]
