#!/usr/bin/env python3
"""Small operational CLI for creating and editing real server accounts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "Server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from projecta.storage.accounts import DEFAULT_DATABASE_URL, PostgresAccountStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Project A PostgreSQL accounts")
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create or update a durable account")
    create.add_argument("account_key")
    create.add_argument("--game-name")
    create.add_argument("--tag-line", default="LOCAL")
    create.add_argument("--subject")

    wallet = sub.add_parser("wallet", help="set a wallet balance")
    wallet.add_argument("account_key")
    wallet.add_argument("item_id")
    wallet.add_argument("amount", type=int)

    entitlement = sub.add_parser("entitlement", help="grant an entitlement")
    entitlement.add_argument("account_key")
    entitlement.add_argument("item_type_id")
    entitlement.add_argument("item_id")
    entitlement.add_argument("--source", default="manual")

    friend = sub.add_parser("friend", help="create a friendship")
    friend.add_argument("account_key_a")
    friend.add_argument("account_key_b")

    show = sub.add_parser("show", help="print account-owned durable data")
    show.add_argument("account_key")

    args = parser.parse_args()
    store = PostgresAccountStore(args.database_url)
    store.migrate()

    if args.command == "create":
        hint = {"key": args.account_key}
        if args.game_name:
            hint["game_name"] = args.game_name
        if args.tag_line:
            hint["tag_line"] = args.tag_line
        if args.subject:
            hint["subject"] = args.subject
        record = store.get_or_create_account(args.account_key, hint)
        if args.game_name or args.tag_line:
            record = store.update_alias(record.account_key, args.game_name or record.game_name, args.tag_line or record.tag_line)
        print(json.dumps(record.__dict__ if hasattr(record, "__dict__") else {
            "account_key": record.account_key,
            "subject": record.subject,
            "game_name": record.game_name,
            "tag_line": record.tag_line,
        }, indent=2))
    elif args.command == "wallet":
        store.get_or_create_account(args.account_key)
        store.set_wallet_balance(args.account_key, args.item_id, args.amount)
        print(json.dumps(store.wallet_balances(args.account_key), indent=2, sort_keys=True))
    elif args.command == "entitlement":
        store.get_or_create_account(args.account_key)
        store.grant_entitlement(args.account_key, args.item_type_id, args.item_id, args.source)
        print(json.dumps(store.entitlements_for_account(args.account_key), indent=2, sort_keys=True))
    elif args.command == "friend":
        store.get_or_create_account(args.account_key_a)
        store.get_or_create_account(args.account_key_b)
        store.add_friend(args.account_key_a, args.account_key_b)
        print("ok")
    elif args.command == "show":
        record = store.get_or_create_account(args.account_key)
        print(json.dumps({
            "account": {
                "account_key": record.account_key,
                "subject": record.subject,
                "game_name": record.game_name,
                "tag_line": record.tag_line,
            },
            "party_id": store.current_party_id(record.account_key),
            "friends": [friend.account_key for friend in store.friends_for_account(record.account_key)],
            "wallet": store.wallet_balances(record.account_key),
            "entitlements": store.entitlements_for_account(record.account_key),
            "loadout": store.get_player_loadout(record.account_key),
            "contract_state": store.contract_state(record.account_key),
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
