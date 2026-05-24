CREATE TABLE IF NOT EXISTS accounts (
    account_key text PRIMARY KEY,
    subject uuid NOT NULL UNIQUE,
    game_name text NOT NULL,
    tag_line text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS parties (
    id uuid PRIMARY KEY,
    owner_account_key text NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    state text NOT NULL DEFAULT 'DEFAULT',
    accessibility text NOT NULL DEFAULT 'CLOSED',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS party_members (
    account_key text PRIMARY KEY REFERENCES accounts(account_key) ON DELETE CASCADE,
    party_id uuid NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    joined_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_party_members_party_id ON party_members(party_id);

CREATE INDEX IF NOT EXISTS idx_accounts_alias ON accounts(lower(game_name), lower(tag_line));

CREATE TABLE IF NOT EXISTS party_invites (
    id uuid PRIMARY KEY,
    party_id uuid NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    inviter_account_key text NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    invitee_account_key text NOT NULL REFERENCES accounts(account_key) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_party_invites_invitee ON party_invites(invitee_account_key);
