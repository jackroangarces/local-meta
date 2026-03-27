CREATE TABLE IF NOT EXISTS regions (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(512) NOT NULL
);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    source VARCHAR(255) NOT NULL,
    ranking_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (region_id, ranking_date)
);

CREATE TABLE IF NOT EXISTS players (
    id BIGSERIAL PRIMARY KEY,
    supermajor_player_id BIGINT NOT NULL UNIQUE,
    current_tag VARCHAR(255) NOT NULL,
    startgg_user_id VARCHAR(64) NULL UNIQUE,
    startgg_player_id BIGINT NULL UNIQUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ranking_entries (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES ranking_snapshots(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    power_rating DOUBLE PRECISION NOT NULL,
    raw_tag VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (snapshot_id, rank)
);

CREATE TABLE IF NOT EXISTS character_usage (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES ranking_snapshots(id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    character_id NUMERIC(4,1) NOT NULL,
    character_name VARCHAR(100) NOT NULL,
    play_percent INTEGER NOT NULL,
    games_played INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (snapshot_id, player_id, character_id),
    CHECK (play_percent >= 0 AND play_percent <= 100),
    CHECK (games_played >= 0)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_ranking_entries_snapshot_id
    ON ranking_entries (snapshot_id);

CREATE INDEX IF NOT EXISTS ix_character_usage_snapshot_id
    ON character_usage (snapshot_id);

CREATE INDEX IF NOT EXISTS ix_character_usage_player_id
    ON character_usage (player_id);

-- Cached “upset” results for Rising Stars.
-- One row per qualifying set, keyed by (snapshot_id, set_id) to keep the
-- computation idempotent.
CREATE TABLE IF NOT EXISTS upsets (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES ranking_snapshots(id) ON DELETE CASCADE,

    winner_player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    defeated_player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,

    set_id BIGINT NOT NULL,

    winner_tag VARCHAR(255) NOT NULL,
    defeated_tag VARCHAR(255) NOT NULL,

    winner_rank INTEGER NOT NULL,
    defeated_rank INTEGER NOT NULL,

    upset_factor INTEGER NOT NULL CHECK (upset_factor >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT upsets_unique_per_snapshot_set UNIQUE (snapshot_id, set_id)
);

CREATE INDEX IF NOT EXISTS ix_upsets_snapshot_winner
    ON upsets (snapshot_id, winner_player_id);

CREATE INDEX IF NOT EXISTS ix_upsets_snapshot_defeated
    ON upsets (snapshot_id, defeated_player_id);

CREATE INDEX IF NOT EXISTS ix_upsets_snapshot_upset_factor
    ON upsets (snapshot_id, upset_factor);

CREATE TABLE IF NOT EXISTS head_to_heads (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES ranking_snapshots(id) ON DELETE CASCADE,

    player1_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    player2_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    CHECK (player1_id < player2_id),

    player1_tag VARCHAR(255) NOT NULL,
    player2_tag VARCHAR(255) NOT NULL,
    player1_rank INTEGER NOT NULL,
    player2_rank INTEGER NOT NULL,

    player1_wins INTEGER NOT NULL DEFAULT 0 CHECK (player1_wins >= 0),
    player2_wins INTEGER NOT NULL DEFAULT 0 CHECK (player2_wins >= 0),
    total_sets INTEGER NOT NULL DEFAULT 0 CHECK (total_sets >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT head_to_heads_unique_pair UNIQUE (snapshot_id, player1_id, player2_id)
);

CREATE INDEX IF NOT EXISTS ix_head_to_heads_snapshot_total_sets
    ON head_to_heads (snapshot_id, total_sets);

CREATE INDEX IF NOT EXISTS ix_head_to_heads_snapshot_player1
    ON head_to_heads (snapshot_id, player1_id);

CREATE INDEX IF NOT EXISTS ix_head_to_heads_snapshot_player2
    ON head_to_heads (snapshot_id, player2_id);

