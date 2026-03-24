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

