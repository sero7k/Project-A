CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS accounts (
    account_key TEXT PRIMARY KEY,
    subject UUID NOT NULL UNIQUE,
    game_name TEXT NOT NULL,
    tag_line TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(account_key) > 0),
    CHECK (length(game_name) > 0),
    CHECK (length(tag_line) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS accounts_alias_unique_idx
    ON accounts (lower(game_name), lower(tag_line));

CREATE TABLE IF NOT EXISTS parties (
    party_id UUID PRIMARY KEY,
    owner_account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    accessibility TEXT NOT NULL DEFAULT 'CLOSED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS party_members (
    party_id UUID NOT NULL REFERENCES parties(party_id) ON DELETE CASCADE,
    account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    is_owner BOOLEAN NOT NULL DEFAULT false,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (party_id, account_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS party_members_one_party_per_account_idx
    ON party_members (account_key);
CREATE INDEX IF NOT EXISTS party_members_party_idx ON party_members (party_id, joined_at);

CREATE TABLE IF NOT EXISTS party_invites (
    invite_id UUID PRIMARY KEY,
    party_id UUID NOT NULL REFERENCES parties(party_id) ON DELETE CASCADE,
    inviter_account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    invitee_account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS party_invites_pending_unique_idx
    ON party_invites (party_id, invitee_account_key)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS party_invites_invitee_idx ON party_invites (invitee_account_key, status, created_at DESC);

CREATE TABLE IF NOT EXISTS friendships (
    account_key_a TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    account_key_b TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_key_a, account_key_b),
    CHECK (account_key_a < account_key_b)
);
CREATE INDEX IF NOT EXISTS friendships_account_b_idx ON friendships (account_key_b);

CREATE TABLE IF NOT EXISTS friend_requests (
    request_id UUID PRIMARY KEY,
    sender_account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    receiver_account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (sender_account_key <> receiver_account_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS friend_requests_pending_unique_idx
    ON friend_requests (sender_account_key, receiver_account_key)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS friend_requests_receiver_idx ON friend_requests (receiver_account_key, status, created_at DESC);
CREATE INDEX IF NOT EXISTS friend_requests_sender_idx ON friend_requests (sender_account_key, status, created_at DESC);

CREATE TABLE IF NOT EXISTS player_loadouts (
    account_key TEXT PRIMARY KEY REFERENCES accounts(account_key) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 0,
    loadout JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS wallet_balances (
    account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    item_id UUID NOT NULL,
    amount BIGINT NOT NULL DEFAULT 0 CHECK (amount >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_key, item_id)
);

CREATE TABLE IF NOT EXISTS entitlements (
    account_key TEXT NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    item_type_id UUID NOT NULL,
    item_id UUID NOT NULL,
    source TEXT NOT NULL DEFAULT 'bootstrap',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_key, item_type_id, item_id)
);
CREATE INDEX IF NOT EXISTS entitlements_account_type_idx ON entitlements (account_key, item_type_id);

CREATE TABLE IF NOT EXISTS contract_states (
    account_key TEXT PRIMARY KEY REFERENCES accounts(account_key) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 0,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    account_key TEXT PRIMARY KEY REFERENCES accounts(account_key) ON DELETE CASCADE,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY,
    cid TEXT NOT NULL,
    sender_account_key TEXT REFERENCES accounts(account_key) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messages_room_idx ON chat_messages (cid, created_at DESC);

CREATE TABLE IF NOT EXISTS server_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
