-- 001: data spine + gate ledger.
-- Forward-only. Never edit an applied migration; add a new numbered one.

-- Canonical club registry. One row per real club; football-data short names and
-- FBref squad names both bridge into this table via team_aliases.
CREATE TABLE teams (
    team_id        INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE
);

-- The hand-maintained bridge. `source` is 'football-data' or 'fbref'.
-- An alias is unique per source; the same club may hold several per source
-- (e.g. fbref writes both 'Torquay United' and 'Torquay').
CREATE TABLE team_aliases (
    source   TEXT NOT NULL,
    alias    TEXT NOT NULL,
    team_id  INTEGER NOT NULL REFERENCES teams(team_id),
    PRIMARY KEY (source, alias)
);

-- Normalised match corpus. Odds columns are era-unified: Betbrain aggregates
-- (2010-11..2018-19) and market Avg/Max (2019-20..) land in the same fields,
-- distinguished by odds_era. Stat columns are NULL where the source omits them
-- (EC has no shots/corners/fouls from 2016-17).
CREATE TABLE matches (
    match_id       TEXT PRIMARY KEY,
    season         TEXT NOT NULL,
    division       TEXT NOT NULL,
    match_date     TEXT NOT NULL,          -- ISO yyyy-mm-dd
    kickoff_time   TEXT,                   -- HH:MM, present from 2019-20 only
    home_team_id   INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id   INTEGER NOT NULL REFERENCES teams(team_id),

    fthg INTEGER, ftag INTEGER, ftr TEXT,
    hthg INTEGER, htag INTEGER, htr TEXT,
    referee TEXT,

    home_shots INTEGER, away_shots INTEGER,
    home_sot   INTEGER, away_sot   INTEGER,
    home_corners INTEGER, away_corners INTEGER,
    home_fouls INTEGER, away_fouls INTEGER,
    home_yellow INTEGER, away_yellow INTEGER,
    home_red INTEGER, away_red INTEGER,

    -- pre-closing (collected Friday/Tuesday PM: BEFORE team news)
    b365_h REAL, b365_d REAL, b365_a REAL,
    ps_h REAL, ps_d REAL, ps_a REAL,
    avg_h REAL, avg_d REAL, avg_a REAL,
    max_h REAL, max_d REAL, max_a REAL,
    avg_over25 REAL, avg_under25 REAL,
    max_over25 REAL, max_under25 REAL,
    ah_line REAL, avg_ah_h REAL, avg_ah_a REAL,

    -- closing (at kickoff: AFTER team news). Pinnacle from 2012-13, the rest
    -- from 2019-20. Pinnacle collapses mid-2025-26, hence the Avg fallback.
    close_ps_h REAL, close_ps_d REAL, close_ps_a REAL,
    close_b365_h REAL, close_b365_d REAL, close_b365_a REAL,
    close_avg_h REAL, close_avg_d REAL, close_avg_a REAL,
    close_max_h REAL, close_max_d REAL, close_max_a REAL,
    close_avg_over25 REAL, close_avg_under25 REAL,
    close_ah_line REAL, close_avg_ah_h REAL, close_avg_ah_a REAL,

    odds_era    TEXT NOT NULL,             -- 'betbrain' | 'market'
    source_file TEXT NOT NULL
);

CREATE INDEX idx_matches_season_div ON matches (season, division);
CREATE INDEX idx_matches_date ON matches (match_date);
CREATE INDEX idx_matches_home ON matches (home_team_id);
CREATE INDEX idx_matches_away ON matches (away_team_id);

-- One row per player per club-spell per season (FBref Standard Stats).
-- Mid-season transfers produce two rows sharing player_id; never group by name.
-- player_id_kind='slug' marks the National League pre-2018-19 pseudo-IDs, which
-- are NOT stable identities and must not be joined across seasons or divisions.
CREATE TABLE player_seasons (
    id             INTEGER PRIMARY KEY,
    season         TEXT NOT NULL,
    division       TEXT NOT NULL,
    player_id      TEXT NOT NULL,
    player_id_kind TEXT NOT NULL,          -- 'hex' | 'slug'
    player_name    TEXT NOT NULL,
    nation         TEXT,
    position       TEXT,
    age            INTEGER,
    born           INTEGER,
    team_id        INTEGER REFERENCES teams(team_id),
    squad_raw      TEXT NOT NULL,

    mp INTEGER, starts INTEGER, minutes INTEGER, nineties REAL,
    goals INTEGER, assists INTEGER, goals_non_pk INTEGER,
    pk INTEGER, pk_att INTEGER, cards_y INTEGER, cards_r INTEGER,

    source_file TEXT NOT NULL
);

CREATE INDEX idx_player_seasons_season_div ON player_seasons (season, division);
CREATE INDEX idx_player_seasons_player ON player_seasons (player_id);
CREATE INDEX idx_player_seasons_team ON player_seasons (team_id, season);

-- Append-only. Records every gate, sweep and exploratory query run against the
-- development set, and every unseal of the holdout. This is what gives the
-- deflated-performance / PBO calculation a real trial count to work from, so it
-- is load-bearing rather than bookkeeping (SPEC §5.3). Never UPDATE or DELETE.
CREATE TABLE gate_ledger (
    id           INTEGER PRIMARY KEY,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    kind         TEXT NOT NULL,            -- 'holdout_unseal' | 'gate' | 'sweep' | 'probe'
    name         TEXT NOT NULL,
    purpose      TEXT,                     -- Purpose of the corpus read
    seasons      TEXT,                     -- comma-separated season codes touched
    divisions    TEXT,
    detail       TEXT,                     -- free-form JSON
    reason       TEXT
);

CREATE INDEX idx_gate_ledger_kind ON gate_ledger (kind);
