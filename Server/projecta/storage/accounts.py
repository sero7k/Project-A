"""PostgreSQL and in-memory persistence backends for the Project A server.

The server imports this module directly.  psycopg is intentionally imported
lazily so the server can still run smoke tests with --allow-memory-db on a
machine that does not have PostgreSQL client libraries installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import hashlib
import os
import re
import threading
import uuid

DEFAULT_DATABASE_URL = os.getenv(
    "PROJECTA_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://projecta:projecta@127.0.0.1:5432/projecta"),
)

_ACCOUNT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project-a-local-account")
_PARTY_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project-a-local-party")
_REQUEST_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "project-a-local-request")


@dataclass(frozen=True, slots=True)
class AccountRecord:
    account_key: str
    subject: str
    game_name: str
    tag_line: str


@dataclass(frozen=True, slots=True)
class FriendRequestRecord:
    request_id: str
    sender_account_key: str
    receiver_account_key: str


@dataclass(frozen=True, slots=True)
class PartyInviteRecord:
    invite_id: str
    inviter_account_key: str
    invitee_account_key: str
    party_id: str


class AccountStore(ABC):
    """Server-facing persistence contract implemented by every storage backend."""

    def close(self) -> None:
        return None

    @abstractmethod
    def migrate(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_or_create_account(self, account_key: str, hint: dict[str, Any] | None = None) -> AccountRecord:
        raise NotImplementedError

    @abstractmethod
    def get_account_by_subject(self, subject: str) -> AccountRecord | None:
        raise NotImplementedError

    @abstractmethod
    def find_account_by_alias(self, game_name: str, tag_line: str) -> AccountRecord | None:
        raise NotImplementedError

    @abstractmethod
    def known_accounts(self) -> list[AccountRecord]:
        raise NotImplementedError

    @abstractmethod
    def update_alias(self, account_key: str, game_name: str, tag_line: str) -> AccountRecord:
        raise NotImplementedError

    @abstractmethod
    def current_party_id(self, account_key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def party_members(self, party_id: str) -> list[AccountRecord]:
        raise NotImplementedError

    @abstractmethod
    def join_party(self, account_key: str, party_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def leave_party(self, account_key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def create_party_invite(self, inviter_account_key: str, invitee_account_key: str, party_id: str) -> PartyInviteRecord:
        raise NotImplementedError

    @abstractmethod
    def invites_for_account(self, account_key: str) -> list[PartyInviteRecord]:
        raise NotImplementedError

    @abstractmethod
    def accept_party_invite(self, account_key: str, invite_id: str) -> PartyInviteRecord | None:
        raise NotImplementedError

    @abstractmethod
    def decline_party_invite(self, account_key: str, invite_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def friends_for_account(self, account_key: str) -> list[AccountRecord]:
        raise NotImplementedError

    @abstractmethod
    def add_friend(self, left_key: str, right_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_friend(self, left_key: str, right_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_friend_request(self, sender_account_key: str, receiver_account_key: str) -> FriendRequestRecord:
        raise NotImplementedError

    @abstractmethod
    def friend_requests_for_account(self, account_key: str, inbound: bool) -> list[FriendRequestRecord]:
        raise NotImplementedError

    @abstractmethod
    def accept_friend_request(self, account_key: str, request_id: str) -> FriendRequestRecord | None:
        raise NotImplementedError

    @abstractmethod
    def decline_friend_request(self, account_key: str, request_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load_state(self, key: str, default: Any | None = None) -> Any:
        raise NotImplementedError

    @abstractmethod
    def save_state(self, key: str, value: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_player_loadout(self, account_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save_player_loadout(self, account_key: str, loadout: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def wallet_balances(self, account_key: str) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def set_wallet_balance(self, account_key: str, item_id: str, amount: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def entitlements_for_account(self, account_key: str, item_type_id: str | None = None) -> list[str] | dict[str, list[str]]:
        raise NotImplementedError

    @abstractmethod
    def grant_entitlement(self, account_key: str, item_type_id: str, item_id: str, source: str = "manual") -> None:
        raise NotImplementedError

    @abstractmethod
    def contract_state(self, account_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save_contract_state(self, account_key: str, state: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_chat_message(self, message: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def chat_messages_for_room(self, cid: str, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError


def normalize_account_key(key: str | None) -> str:
    raw = str(key or "developer").strip().lower()
    raw = re.sub(r"[^a-z0-9_.@-]+", "-", raw).strip("-._")
    return raw or "developer"


def generated_subject(key: str | None) -> str:
    return str(uuid.uuid5(_ACCOUNT_NAMESPACE, normalize_account_key(key)))


def generated_party_id(subject: str | None) -> str:
    try:
        normalized = str(uuid.UUID(str(subject)))
    except (TypeError, ValueError):
        normalized = generated_subject(str(subject or "developer"))
    return str(uuid.uuid5(_PARTY_NAMESPACE, normalized))


def _short_hash(*parts: Any, length: int = 8) -> str:
    raw = "\0".join(str(part) for part in parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:length]


def _default_alias_for_key(key: str) -> tuple[str, str]:
    key = normalize_account_key(key)
    if key in {"developer", "developer1", "dev1", "player1", "p1"}:
        return "DevPlayer", "LOCAL"
    if key in {"developer2", "dev2", "player2", "p2"}:
        return "DevPlayer2", "LOCAL"
    safe = re.sub(r"[^A-Za-z0-9]", "", key)[:12] or "Player"
    return f"{safe[:1].upper()}{safe[1:]}{_short_hash(key, length=4)}", "LOCAL"


def account_from_hint(key: str | None, hint: dict[str, Any] | None = None) -> AccountRecord:
    account_key = normalize_account_key(key or (hint or {}).get("key"))
    hint = hint or {}
    subject = str(hint.get("subject") or hint.get("Subject") or generated_subject(account_key))
    default_name, default_tag = _default_alias_for_key(account_key)
    game_name = str(
        hint.get("game_name")
        or hint.get("gameName")
        or hint.get("GameName")
        or hint.get("name")
        or default_name
    ).strip() or default_name
    tag_line = str(
        hint.get("tag_line")
        or hint.get("tagLine")
        or hint.get("TagLine")
        or hint.get("tag")
        or default_tag
    ).strip() or default_tag
    return AccountRecord(account_key=account_key, subject=str(uuid.UUID(subject)), game_name=game_name, tag_line=tag_line)


def _ordered_pair(left: str, right: str) -> tuple[str, str]:
    left = normalize_account_key(left)
    right = normalize_account_key(right)
    if left == right:
        raise ValueError("an account cannot friend itself")
    return (left, right) if left < right else (right, left)


def _record_from_row(row: dict[str, Any]) -> AccountRecord:
    return AccountRecord(
        account_key=str(row["account_key"]),
        subject=str(row["subject"]),
        game_name=str(row["game_name"]),
        tag_line=str(row["tag_line"]),
    )


class MemoryAccountStore(AccountStore):
    """Thread-safe in-memory backend with the same behavior as PostgresAccountStore."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.accounts: dict[str, AccountRecord] = {}
        self._subject_to_key: dict[str, str] = {}
        self._alias_to_key: dict[tuple[str, str], str] = {}
        self._friendships: set[tuple[str, str]] = set()
        self._friend_requests: dict[str, tuple[FriendRequestRecord, str]] = {}
        self._account_party: dict[str, str] = {}
        self._parties: dict[str, dict[str, Any]] = {}
        self._party_invites: dict[str, tuple[PartyInviteRecord, str]] = {}
        self._server_state: dict[str, Any] = {}
        self._loadouts: dict[str, dict[str, Any]] = {}
        self._wallets: dict[str, dict[str, int]] = {}
        self._entitlements: dict[str, dict[str, set[str]]] = {}
        self._contracts: dict[str, dict[str, Any]] = {}
        self._chat_messages: list[dict[str, Any]] = []

    def migrate(self) -> None:
        return None

    def _ensure_account_locked(self, account_key: str, hint: dict[str, Any] | None = None) -> AccountRecord:
        key = normalize_account_key(account_key)
        existing = self.accounts.get(key)
        if existing:
            return existing
        record = account_from_hint(key, hint)
        alias_key = (record.game_name.lower(), record.tag_line.lower())
        if alias_key in self._alias_to_key:
            record = AccountRecord(record.account_key, record.subject, f"{record.game_name}{_short_hash(key, length=4)}", record.tag_line)
            alias_key = (record.game_name.lower(), record.tag_line.lower())
        self.accounts[key] = record
        self._subject_to_key[record.subject.lower()] = key
        self._alias_to_key[alias_key] = key
        party_id = generated_party_id(record.subject)
        self._parties.setdefault(party_id, {"owner": key, "members": []})
        if key not in self._parties[party_id]["members"]:
            self._parties[party_id]["members"].append(key)
        self._account_party[key] = party_id
        return record

    def get_or_create_account(self, account_key: str, hint: dict[str, Any] | None = None) -> AccountRecord:
        with self._lock:
            return self._ensure_account_locked(account_key, hint)

    def get_account_by_subject(self, subject: str) -> AccountRecord | None:
        with self._lock:
            key = self._subject_to_key.get(str(subject).lower())
            return self.accounts.get(key) if key else None

    def find_account_by_alias(self, game_name: str, tag_line: str) -> AccountRecord | None:
        with self._lock:
            key = self._alias_to_key.get((str(game_name).lower(), str(tag_line).lower()))
            return self.accounts.get(key) if key else None

    def known_accounts(self) -> list[AccountRecord]:
        with self._lock:
            return sorted(self.accounts.values(), key=lambda r: r.account_key)

    def update_alias(self, account_key: str, game_name: str, tag_line: str) -> AccountRecord:
        with self._lock:
            current = self._ensure_account_locked(account_key)
            alias_key = (str(game_name).lower(), str(tag_line).lower())
            owner = self._alias_to_key.get(alias_key)
            if owner and owner != current.account_key:
                return current
            self._alias_to_key.pop((current.game_name.lower(), current.tag_line.lower()), None)
            updated = AccountRecord(current.account_key, current.subject, str(game_name), str(tag_line))
            self.accounts[current.account_key] = updated
            self._alias_to_key[alias_key] = current.account_key
            return updated

    def current_party_id(self, account_key: str) -> str:
        with self._lock:
            record = self._ensure_account_locked(account_key)
            return self._account_party.setdefault(record.account_key, generated_party_id(record.subject))

    def party_members(self, party_id: str) -> list[AccountRecord]:
        with self._lock:
            party = self._parties.get(str(party_id), {"members": []})
            return [self.accounts[key] for key in party.get("members", []) if key in self.accounts]

    def join_party(self, account_key: str, party_id: str) -> str:
        with self._lock:
            record = self._ensure_account_locked(account_key)
            old_party = self._account_party.get(record.account_key)
            if old_party and old_party in self._parties:
                self._parties[old_party]["members"] = [k for k in self._parties[old_party].get("members", []) if k != record.account_key]
            party = self._parties.setdefault(str(party_id), {"owner": record.account_key, "members": []})
            if record.account_key not in party["members"]:
                party["members"].append(record.account_key)
            self._account_party[record.account_key] = str(party_id)
            return str(party_id)

    def leave_party(self, account_key: str) -> str:
        with self._lock:
            record = self._ensure_account_locked(account_key)
            new_party = generated_party_id(record.subject)
            return self.join_party(record.account_key, new_party)

    def create_party_invite(self, inviter_account_key: str, invitee_account_key: str, party_id: str) -> PartyInviteRecord:
        with self._lock:
            inviter = self._ensure_account_locked(inviter_account_key)
            invitee = self._ensure_account_locked(invitee_account_key)
            for record, status in self._party_invites.values():
                if record.party_id == str(party_id) and record.invitee_account_key == invitee.account_key and status == "pending":
                    return record
            invite_id = str(uuid.uuid4())
            record = PartyInviteRecord(invite_id, inviter.account_key, invitee.account_key, str(party_id))
            self._party_invites[invite_id] = (record, "pending")
            return record

    def invites_for_account(self, account_key: str) -> list[PartyInviteRecord]:
        with self._lock:
            key = normalize_account_key(account_key)
            return [record for record, status in self._party_invites.values() if status == "pending" and record.invitee_account_key == key]

    def accept_party_invite(self, account_key: str, invite_id: str) -> PartyInviteRecord | None:
        with self._lock:
            pair = self._party_invites.get(str(invite_id))
            if not pair:
                return None
            record, status = pair
            if status != "pending" or record.invitee_account_key != normalize_account_key(account_key):
                return None
            self._party_invites[str(invite_id)] = (record, "accepted")
            self.join_party(account_key, record.party_id)
            return record

    def decline_party_invite(self, account_key: str, invite_id: str) -> bool:
        with self._lock:
            pair = self._party_invites.get(str(invite_id))
            if not pair:
                return False
            record, status = pair
            if status != "pending" or record.invitee_account_key != normalize_account_key(account_key):
                return False
            self._party_invites[str(invite_id)] = (record, "declined")
            return True

    def friends_for_account(self, account_key: str) -> list[AccountRecord]:
        with self._lock:
            key = normalize_account_key(account_key)
            friend_keys = [b if a == key else a for a, b in self._friendships if key in (a, b)]
            return [self.accounts[f] for f in sorted(friend_keys) if f in self.accounts]

    def add_friend(self, left_key: str, right_key: str) -> None:
        with self._lock:
            self._ensure_account_locked(left_key)
            self._ensure_account_locked(right_key)
            self._friendships.add(_ordered_pair(left_key, right_key))

    def remove_friend(self, left_key: str, right_key: str) -> bool:
        with self._lock:
            pair = _ordered_pair(left_key, right_key)
            existed = pair in self._friendships
            self._friendships.discard(pair)
            return existed

    def create_friend_request(self, sender_account_key: str, receiver_account_key: str) -> FriendRequestRecord:
        with self._lock:
            sender = self._ensure_account_locked(sender_account_key)
            receiver = self._ensure_account_locked(receiver_account_key)
            for record, status in self._friend_requests.values():
                if status == "pending" and record.sender_account_key == sender.account_key and record.receiver_account_key == receiver.account_key:
                    return record
            record = FriendRequestRecord(str(uuid.uuid4()), sender.account_key, receiver.account_key)
            self._friend_requests[record.request_id] = (record, "pending")
            return record

    def friend_requests_for_account(self, account_key: str, inbound: bool) -> list[FriendRequestRecord]:
        with self._lock:
            key = normalize_account_key(account_key)
            if inbound:
                return [r for r, s in self._friend_requests.values() if s == "pending" and r.receiver_account_key == key]
            return [r for r, s in self._friend_requests.values() if s == "pending" and r.sender_account_key == key]

    def accept_friend_request(self, account_key: str, request_id: str) -> FriendRequestRecord | None:
        with self._lock:
            pair = self._friend_requests.get(str(request_id))
            if not pair:
                return None
            record, status = pair
            if status != "pending" or normalize_account_key(account_key) not in {record.receiver_account_key, record.sender_account_key}:
                return None
            self._friend_requests[str(request_id)] = (record, "accepted")
            self.add_friend(record.sender_account_key, record.receiver_account_key)
            return record

    def decline_friend_request(self, account_key: str, request_id: str) -> bool:
        with self._lock:
            pair = self._friend_requests.get(str(request_id))
            if not pair:
                return False
            record, status = pair
            if status != "pending" or normalize_account_key(account_key) not in {record.receiver_account_key, record.sender_account_key}:
                return False
            self._friend_requests[str(request_id)] = (record, "declined")
            return True

    def load_state(self, key: str, default: Any | None = None) -> Any:
        with self._lock:
            return self._server_state.get(key, default)

    def save_state(self, key: str, value: Any) -> None:
        with self._lock:
            self._server_state[key] = value

    def get_player_loadout(self, account_key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._loadouts.get(normalize_account_key(account_key))
            return dict(value) if isinstance(value, dict) else None

    def save_player_loadout(self, account_key: str, loadout: dict[str, Any]) -> None:
        with self._lock:
            self._loadouts[normalize_account_key(account_key)] = dict(loadout)

    def wallet_balances(self, account_key: str) -> dict[str, int]:
        with self._lock:
            return dict(self._wallets.get(normalize_account_key(account_key), {}))

    def set_wallet_balance(self, account_key: str, item_id: str, amount: int) -> None:
        with self._lock:
            self._wallets.setdefault(normalize_account_key(account_key), {})[str(item_id)] = max(0, int(amount))

    def entitlements_for_account(self, account_key: str, item_type_id: str | None = None) -> list[str] | dict[str, list[str]]:
        with self._lock:
            entitlements = self._entitlements.get(normalize_account_key(account_key), {})
            if item_type_id:
                return sorted(entitlements.get(str(item_type_id).lower(), set()))
            return {k: sorted(v) for k, v in entitlements.items()}

    def grant_entitlement(self, account_key: str, item_type_id: str, item_id: str, source: str = "manual") -> None:
        with self._lock:
            self._entitlements.setdefault(normalize_account_key(account_key), {}).setdefault(str(item_type_id).lower(), set()).add(str(item_id))

    def contract_state(self, account_key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._contracts.get(normalize_account_key(account_key))
            return dict(value) if isinstance(value, dict) else None

    def save_contract_state(self, account_key: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._contracts[normalize_account_key(account_key)] = dict(state)

    def append_chat_message(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._chat_messages.append(dict(message))

    def chat_messages_for_room(self, cid: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [m for m in self._chat_messages if m.get("cid") == cid or m.get("Cid") == cid][-limit:]


class PostgresAccountStore(AccountStore):
    """PostgreSQL implementation used by the production compatibility server."""

    def __init__(self, database_url: str | None = None, *, min_pool: int = 1, max_pool: int = 8) -> None:
        self.database_url = database_url or DEFAULT_DATABASE_URL
        self._min_pool = min_pool
        self._max_pool = max_pool
        self._pool: Any | None = None
        self._pool_lock = threading.Lock()

    @property
    def pool(self) -> Any:
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    try:
                        from psycopg.rows import dict_row
                        from psycopg_pool import ConnectionPool
                    except Exception as exc:  # pragma: no cover - only hit on missing optional dependency
                        raise RuntimeError(
                            "PostgreSQL mode requires psycopg[binary,pool]. Install requirements.txt "
                            "or run with --allow-memory-db for smoke tests."
                        ) from exc
                    self._pool = ConnectionPool(
                        conninfo=self.database_url,
                        min_size=self._min_pool,
                        max_size=self._max_pool,
                        kwargs={"row_factory": dict_row, "autocommit": False},
                        open=True,
                    )
        return self._pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def migrate(self) -> None:
        schema_path = Path(__file__).resolve().parent / "sql" / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        with self.pool.connection() as conn:
            conn.execute(schema_sql)
            conn.commit()

    def _ensure_account_tx(self, cur: Any, account_key: str, hint: dict[str, Any] | None = None) -> AccountRecord:
        key = normalize_account_key(account_key)
        row = cur.execute("SELECT * FROM accounts WHERE account_key = %s", (key,)).fetchone()
        if row:
            return _record_from_row(row)
        record = account_from_hint(key, hint)
        alias_owner = cur.execute(
            "SELECT account_key FROM accounts WHERE lower(game_name) = lower(%s) AND lower(tag_line) = lower(%s)",
            (record.game_name, record.tag_line),
        ).fetchone()
        if alias_owner:
            record = AccountRecord(record.account_key, record.subject, f"{record.game_name}{_short_hash(key, length=4)}", record.tag_line)
        row = cur.execute(
            """
            INSERT INTO accounts (account_key, subject, game_name, tag_line)
            VALUES (%s, %s::uuid, %s, %s)
            RETURNING *
            """,
            (record.account_key, record.subject, record.game_name, record.tag_line),
        ).fetchone()
        persisted = _record_from_row(row)
        self._ensure_self_party_tx(cur, persisted)
        self._seed_account_defaults_tx(cur, persisted)
        return persisted

    def _ensure_self_party_tx(self, cur: Any, account: AccountRecord) -> str:
        party_id = generated_party_id(account.subject)
        cur.execute(
            """
            INSERT INTO parties (party_id, owner_account_key)
            VALUES (%s::uuid, %s)
            ON CONFLICT (party_id) DO NOTHING
            """,
            (party_id, account.account_key),
        )
        cur.execute(
            """
            INSERT INTO party_members (party_id, account_key, is_owner)
            VALUES (%s::uuid, %s, true)
            ON CONFLICT (account_key) DO NOTHING
            """,
            (party_id, account.account_key),
        )
        return party_id

    def _seed_account_defaults_tx(self, cur: Any, account: AccountRecord) -> None:
        cur.execute(
            """
            INSERT INTO player_loadouts (account_key, version, loadout)
            VALUES (%s, 0, '{}'::jsonb)
            ON CONFLICT (account_key) DO NOTHING
            """,
            (account.account_key,),
        )
        cur.execute(
            """
            INSERT INTO contract_states (account_key, version, state)
            VALUES (%s, 0, '{}'::jsonb)
            ON CONFLICT (account_key) DO NOTHING
            """,
            (account.account_key,),
        )

    def get_or_create_account(self, account_key: str, hint: dict[str, Any] | None = None) -> AccountRecord:
        with self.pool.connection() as conn:
            with conn.transaction():
                return self._ensure_account_tx(conn, account_key, hint)

    def get_account_by_subject(self, subject: str) -> AccountRecord | None:
        try:
            subject_uuid = str(uuid.UUID(str(subject)))
        except (TypeError, ValueError):
            return None
        with self.pool.connection() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE subject = %s::uuid", (subject_uuid,)).fetchone()
            return _record_from_row(row) if row else None

    def find_account_by_alias(self, game_name: str, tag_line: str) -> AccountRecord | None:
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE lower(game_name) = lower(%s) AND lower(tag_line) = lower(%s)",
                (str(game_name), str(tag_line)),
            ).fetchone()
            return _record_from_row(row) if row else None

    def known_accounts(self) -> list[AccountRecord]:
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY account_key").fetchall()
            return [_record_from_row(row) for row in rows]

    def update_alias(self, account_key: str, game_name: str, tag_line: str) -> AccountRecord:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                current = self._ensure_account_tx(conn, key)
                owner = conn.execute(
                    """
                    SELECT account_key FROM accounts
                    WHERE lower(game_name) = lower(%s) AND lower(tag_line) = lower(%s) AND account_key <> %s
                    """,
                    (str(game_name), str(tag_line), key),
                ).fetchone()
                if owner:
                    return current
                row = conn.execute(
                    """
                    UPDATE accounts
                    SET game_name = %s, tag_line = %s, updated_at = now()
                    WHERE account_key = %s
                    RETURNING *
                    """,
                    (str(game_name), str(tag_line), key),
                ).fetchone()
                return _record_from_row(row)

    def current_party_id(self, account_key: str) -> str:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                account = self._ensure_account_tx(conn, key)
                row = conn.execute("SELECT party_id FROM party_members WHERE account_key = %s", (key,)).fetchone()
                if row:
                    return str(row["party_id"])
                return self._ensure_self_party_tx(conn, account)

    def party_members(self, party_id: str) -> list[AccountRecord]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT a.*
                FROM party_members pm
                JOIN accounts a ON a.account_key = pm.account_key
                WHERE pm.party_id = %s::uuid
                ORDER BY pm.is_owner DESC, pm.joined_at ASC, a.account_key ASC
                """,
                (str(party_id),),
            ).fetchall()
            return [_record_from_row(row) for row in rows]

    def join_party(self, account_key: str, party_id: str) -> str:
        key = normalize_account_key(account_key)
        party_id = str(uuid.UUID(str(party_id)))
        with self.pool.connection() as conn:
            with conn.transaction():
                account = self._ensure_account_tx(conn, key)
                owner = conn.execute("SELECT owner_account_key FROM parties WHERE party_id = %s::uuid", (party_id,)).fetchone()
                if not owner:
                    conn.execute(
                        "INSERT INTO parties (party_id, owner_account_key) VALUES (%s::uuid, %s) ON CONFLICT DO NOTHING",
                        (party_id, key),
                    )
                conn.execute(
                    """
                    INSERT INTO party_members (party_id, account_key, is_owner)
                    VALUES (%s::uuid, %s, false)
                    ON CONFLICT (account_key) DO UPDATE
                    SET party_id = EXCLUDED.party_id,
                        is_owner = false,
                        joined_at = now()
                    """,
                    (party_id, account.account_key),
                )
                conn.execute("UPDATE parties SET updated_at = now() WHERE party_id = %s::uuid", (party_id,))
                return party_id

    def leave_party(self, account_key: str) -> str:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                account = self._ensure_account_tx(conn, key)
                party_id = self._ensure_self_party_tx(conn, account)
                conn.execute(
                    """
                    INSERT INTO party_members (party_id, account_key, is_owner)
                    VALUES (%s::uuid, %s, true)
                    ON CONFLICT (account_key) DO UPDATE
                    SET party_id = EXCLUDED.party_id,
                        is_owner = true,
                        joined_at = now()
                    """,
                    (party_id, key),
                )
                return party_id

    def create_party_invite(self, inviter_account_key: str, invitee_account_key: str, party_id: str) -> PartyInviteRecord:
        inviter_key = normalize_account_key(inviter_account_key)
        invitee_key = normalize_account_key(invitee_account_key)
        party_id = str(uuid.UUID(str(party_id)))
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, inviter_key)
                self._ensure_account_tx(conn, invitee_key)
                existing = conn.execute(
                    """
                    SELECT * FROM party_invites
                    WHERE party_id = %s::uuid AND invitee_account_key = %s AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (party_id, invitee_key),
                ).fetchone()
                if existing:
                    return PartyInviteRecord(str(existing["invite_id"]), str(existing["inviter_account_key"]), str(existing["invitee_account_key"]), str(existing["party_id"]))
                invite_id = str(uuid.uuid4())
                row = conn.execute(
                    """
                    INSERT INTO party_invites (invite_id, party_id, inviter_account_key, invitee_account_key)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    RETURNING *
                    """,
                    (invite_id, party_id, inviter_key, invitee_key),
                ).fetchone()
                return PartyInviteRecord(str(row["invite_id"]), str(row["inviter_account_key"]), str(row["invitee_account_key"]), str(row["party_id"]))

    def invites_for_account(self, account_key: str) -> list[PartyInviteRecord]:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM party_invites
                WHERE invitee_account_key = %s AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (key,),
            ).fetchall()
            return [PartyInviteRecord(str(r["invite_id"]), str(r["inviter_account_key"]), str(r["invitee_account_key"]), str(r["party_id"])) for r in rows]

    def accept_party_invite(self, account_key: str, invite_id: str) -> PartyInviteRecord | None:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE party_invites
                    SET status = 'accepted', updated_at = now()
                    WHERE invite_id = %s::uuid AND invitee_account_key = %s AND status = 'pending'
                    RETURNING *
                    """,
                    (str(invite_id), key),
                ).fetchone()
                if not row:
                    return None
                record = PartyInviteRecord(
                    str(row["invite_id"]),
                    str(row["inviter_account_key"]),
                    str(row["invitee_account_key"]),
                    str(row["party_id"]),
                )
                self._ensure_account_tx(conn, key)
                conn.execute(
                    """
                    INSERT INTO party_members (party_id, account_key, is_owner)
                    VALUES (%s::uuid, %s, false)
                    ON CONFLICT (account_key) DO UPDATE
                    SET party_id = EXCLUDED.party_id,
                        is_owner = false,
                        joined_at = now()
                    """,
                    (record.party_id, key),
                )
                conn.execute("UPDATE parties SET updated_at = now() WHERE party_id = %s::uuid", (record.party_id,))
                return record

    def decline_party_invite(self, account_key: str, invite_id: str) -> bool:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE party_invites SET status = 'declined', updated_at = now()
                    WHERE invite_id = %s::uuid AND invitee_account_key = %s AND status = 'pending'
                    RETURNING invite_id
                    """,
                    (str(invite_id), key),
                ).fetchone()
                return row is not None

    def friends_for_account(self, account_key: str) -> list[AccountRecord]:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT a.*
                FROM friendships f
                JOIN accounts a ON a.account_key = CASE WHEN f.account_key_a = %s THEN f.account_key_b ELSE f.account_key_a END
                WHERE f.account_key_a = %s OR f.account_key_b = %s
                ORDER BY a.game_name, a.tag_line
                """,
                (key, key, key),
            ).fetchall()
            return [_record_from_row(row) for row in rows]

    def add_friend(self, left_key: str, right_key: str) -> None:
        a, b = _ordered_pair(left_key, right_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, a)
                self._ensure_account_tx(conn, b)
                conn.execute(
                    """
                    INSERT INTO friendships (account_key_a, account_key_b)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (a, b),
                )

    def remove_friend(self, left_key: str, right_key: str) -> bool:
        a, b = _ordered_pair(left_key, right_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                result = conn.execute("DELETE FROM friendships WHERE account_key_a = %s AND account_key_b = %s", (a, b))
                return result.rowcount > 0

    def create_friend_request(self, sender_account_key: str, receiver_account_key: str) -> FriendRequestRecord:
        sender_key = normalize_account_key(sender_account_key)
        receiver_key = normalize_account_key(receiver_account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, sender_key)
                self._ensure_account_tx(conn, receiver_key)
                existing = conn.execute(
                    """
                    SELECT * FROM friend_requests
                    WHERE sender_account_key = %s AND receiver_account_key = %s AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (sender_key, receiver_key),
                ).fetchone()
                if existing:
                    return FriendRequestRecord(str(existing["request_id"]), str(existing["sender_account_key"]), str(existing["receiver_account_key"]))
                request_id = str(uuid.uuid4())
                row = conn.execute(
                    """
                    INSERT INTO friend_requests (request_id, sender_account_key, receiver_account_key)
                    VALUES (%s::uuid, %s, %s)
                    RETURNING *
                    """,
                    (request_id, sender_key, receiver_key),
                ).fetchone()
                return FriendRequestRecord(str(row["request_id"]), str(row["sender_account_key"]), str(row["receiver_account_key"]))

    def friend_requests_for_account(self, account_key: str, inbound: bool) -> list[FriendRequestRecord]:
        key = normalize_account_key(account_key)
        column = "receiver_account_key" if inbound else "sender_account_key"
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM friend_requests
                WHERE {column} = %s AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (key,),
            ).fetchall()
            return [FriendRequestRecord(str(r["request_id"]), str(r["sender_account_key"]), str(r["receiver_account_key"])) for r in rows]

    def accept_friend_request(self, account_key: str, request_id: str) -> FriendRequestRecord | None:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'accepted', updated_at = now()
                    WHERE request_id = %s::uuid
                      AND status = 'pending'
                      AND (sender_account_key = %s OR receiver_account_key = %s)
                    RETURNING *
                    """,
                    (str(request_id), key, key),
                ).fetchone()
                if not row:
                    return None
                record = FriendRequestRecord(str(row["request_id"]), str(row["sender_account_key"]), str(row["receiver_account_key"]))
                a, b = _ordered_pair(record.sender_account_key, record.receiver_account_key)
                conn.execute(
                    "INSERT INTO friendships (account_key_a, account_key_b) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (a, b),
                )
                return record

    def decline_friend_request(self, account_key: str, request_id: str) -> bool:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE friend_requests
                    SET status = 'declined', updated_at = now()
                    WHERE request_id = %s::uuid
                      AND status = 'pending'
                      AND (sender_account_key = %s OR receiver_account_key = %s)
                    RETURNING request_id
                    """,
                    (str(request_id), key, key),
                ).fetchone()
                return row is not None

    def load_state(self, key: str, default: Any | None = None) -> Any:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT value FROM server_state WHERE key = %s", (str(key),)).fetchone()
            return row["value"] if row else default

    def save_state(self, key: str, value: Any) -> None:
        from psycopg.types.json import Jsonb
        with self.pool.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO server_state (key, value, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = now()
                    """,
                    (str(key), Jsonb(value)),
                )

    def get_player_loadout(self, account_key: str) -> dict[str, Any] | None:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            row = conn.execute("SELECT loadout FROM player_loadouts WHERE account_key = %s", (key,)).fetchone()
            return dict(row["loadout"]) if row and isinstance(row["loadout"], dict) else None

    def save_player_loadout(self, account_key: str, loadout: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, key)
                version = int(loadout.get("Version") or loadout.get("version") or 0)
                conn.execute(
                    """
                    INSERT INTO player_loadouts (account_key, version, loadout, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (account_key) DO UPDATE
                    SET version = EXCLUDED.version, loadout = EXCLUDED.loadout, updated_at = now()
                    """,
                    (key, version, Jsonb(loadout)),
                )

    def wallet_balances(self, account_key: str) -> dict[str, int]:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT item_id, amount FROM wallet_balances WHERE account_key = %s", (key,)).fetchall()
            return {str(row["item_id"]): int(row["amount"]) for row in rows}

    def set_wallet_balance(self, account_key: str, item_id: str, amount: int) -> None:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, key)
                conn.execute(
                    """
                    INSERT INTO wallet_balances (account_key, item_id, amount, updated_at)
                    VALUES (%s, %s::uuid, %s, now())
                    ON CONFLICT (account_key, item_id) DO UPDATE
                    SET amount = EXCLUDED.amount, updated_at = now()
                    """,
                    (key, str(item_id), max(0, int(amount))),
                )

    def entitlements_for_account(self, account_key: str, item_type_id: str | None = None) -> list[str] | dict[str, list[str]]:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            if item_type_id:
                rows = conn.execute(
                    "SELECT item_id FROM entitlements WHERE account_key = %s AND item_type_id = %s::uuid ORDER BY item_id",
                    (key, str(item_type_id)),
                ).fetchall()
                return [str(row["item_id"]) for row in rows]
            rows = conn.execute(
                "SELECT item_type_id, item_id FROM entitlements WHERE account_key = %s ORDER BY item_type_id, item_id",
                (key,),
            ).fetchall()
        by_type: dict[str, list[str]] = {}
        for row in rows:
            by_type.setdefault(str(row["item_type_id"]), []).append(str(row["item_id"]))
        return by_type

    def grant_entitlement(self, account_key: str, item_type_id: str, item_id: str, source: str = "manual") -> None:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, key)
                conn.execute(
                    """
                    INSERT INTO entitlements (account_key, item_type_id, item_id, source)
                    VALUES (%s, %s::uuid, %s::uuid, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (key, str(item_type_id), str(item_id), str(source)),
                )

    def contract_state(self, account_key: str) -> dict[str, Any] | None:
        key = normalize_account_key(account_key)
        with self.pool.connection() as conn:
            row = conn.execute("SELECT state FROM contract_states WHERE account_key = %s", (key,)).fetchone()
            return dict(row["state"]) if row and isinstance(row["state"], dict) else None

    def save_contract_state(self, account_key: str, state: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        key = normalize_account_key(account_key)
        version = int(state.get("Version") or state.get("version") or 0)
        with self.pool.connection() as conn:
            with conn.transaction():
                self._ensure_account_tx(conn, key)
                conn.execute(
                    """
                    INSERT INTO contract_states (account_key, version, state, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (account_key) DO UPDATE
                    SET version = EXCLUDED.version, state = EXCLUDED.state, updated_at = now()
                    """,
                    (key, version, Jsonb(state)),
                )

    def append_chat_message(self, message: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        message_id = str(message.get("id") or message.get("ID") or message.get("messageID") or uuid.uuid4())
        cid = str(message.get("cid") or message.get("Cid") or message.get("Room") or "")
        sender_subject = str(message.get("sender") or message.get("Sender") or "")
        sender_key = None
        if sender_subject:
            account = self.get_account_by_subject(sender_subject)
            sender_key = account.account_key if account else None
        with self.pool.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO chat_messages (message_id, cid, sender_account_key, payload)
                    VALUES (%s::uuid, %s, %s, %s)
                    ON CONFLICT (message_id) DO UPDATE
                    SET payload = EXCLUDED.payload
                    """,
                    (message_id, cid, sender_key, Jsonb(message)),
                )

    def chat_messages_for_room(self, cid: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM chat_messages
                WHERE cid = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (str(cid), int(limit)),
            ).fetchall()
            return [dict(row["payload"]) for row in reversed(rows) if isinstance(row["payload"], dict)]


def create_account_store(database_url: str | None = None, *, allow_memory_db: bool = False) -> AccountStore:
    """Build the configured storage backend without exposing concrete classes to callers."""
    if allow_memory_db:
        return MemoryAccountStore()
    return PostgresAccountStore(database_url or DEFAULT_DATABASE_URL)
