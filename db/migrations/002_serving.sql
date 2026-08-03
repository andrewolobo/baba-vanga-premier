-- 002: the serving path -- fixtures, predictions, the paper book, CLV grades.
-- Forward-only. Never edit an applied migration; add a new numbered one.

-- Upcoming matches pulled from football-data.co.uk's rolling fixtures feed.
-- Separate from `matches` on purpose: a fixture has no result, and letting the
-- two share a table would mean every query over the corpus had to remember to
-- exclude unplayed rows. When the result arrives the grader writes it into
-- `matches` and links back by fixture_id.
--
-- The feed is a ~7-day rolling window and republishes the same fixture with
-- updated prices, so upserts on (division, match_date, home, away) are the
-- normal case rather than an error.
CREATE TABLE fixtures (
    fixture_id     INTEGER PRIMARY KEY,
    division       TEXT NOT NULL,
    match_date     TEXT NOT NULL,          -- ISO yyyy-mm-dd
    kickoff_time   TEXT,                   -- HH:MM as published
    home_team_id   INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id   INTEGER NOT NULL REFERENCES teams(team_id),
    -- Pre-close prices as published with the fixture. Same unified schema as
    -- `matches`, so engine.odds reads both without branching.
    avg_h          REAL,
    avg_d          REAL,
    avg_a          REAL,
    max_h          REAL,
    max_d          REAL,
    max_a          REAL,
    avg_over25     REAL,
    avg_under25    REAL,
    ah_line        REAL,
    avg_ah_h       REAL,
    avg_ah_a       REAL,
    first_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    source_file    TEXT NOT NULL,
    UNIQUE (division, match_date, home_team_id, away_team_id)
);

CREATE INDEX idx_fixtures_date ON fixtures (match_date);

-- Append-only. One row per (fixture, artifact, information set) served.
-- Lambdas are stored RAW so that any later pmf change -- a different line, a
-- correction, a calibration -- can be recomputed from what the model actually
-- said, rather than from probabilities that have already been rounded through
-- one particular derivation.
CREATE TABLE predictions (
    prediction_id   INTEGER PRIMARY KEY,
    fixture_id      INTEGER NOT NULL REFERENCES fixtures(fixture_id),
    served_at       TEXT NOT NULL DEFAULT (datetime('now')),
    model_version   TEXT NOT NULL,          -- artifact version string
    information_set TEXT NOT NULL,          -- 'pre_close' | 'closing'
    lam_h           REAL NOT NULL,
    lam_a           REAL NOT NULL,
    p_home          REAL NOT NULL,
    p_draw          REAL NOT NULL,
    p_away          REAL NOT NULL,
    p_over25        REAL NOT NULL,
    p_under25       REAL NOT NULL,
    calibrated      INTEGER NOT NULL DEFAULT 0,   -- 0 until P3 lands
    UNIQUE (fixture_id, model_version, information_set, served_at)
);

CREATE INDEX idx_predictions_fixture ON predictions (fixture_id);

-- Append-only paper book. Grading columns are written BESIDE the bet, never
-- over it: the price and probability that justified the bet must survive
-- whatever happened next, or the record cannot be audited.
--
-- `breakeven_prob` is the RAW 1/odds -- vig-inclusive -- because that is the
-- bar a bet actually has to clear. It is deliberately not the de-vigged
-- probability, which is the market's opinion and belongs in CLV, not here.
-- Conflating the two is the single easiest way to manufacture a fictional edge.
CREATE TABLE paper_bets (
    bet_id          INTEGER PRIMARY KEY,
    prediction_id   INTEGER NOT NULL REFERENCES predictions(prediction_id),
    fixture_id      INTEGER NOT NULL REFERENCES fixtures(fixture_id),
    placed_at       TEXT NOT NULL DEFAULT (datetime('now')),
    market          TEXT NOT NULL,          -- '1x2' | 'ou25'
    side            TEXT NOT NULL,          -- 'H'|'D'|'A'|'over'|'under'
    price           REAL NOT NULL,          -- decimal odds taken
    price_source    TEXT NOT NULL,          -- which column the price came from
    model_prob      REAL NOT NULL,
    breakeven_prob  REAL NOT NULL,          -- 1/price, VIG-INCLUSIVE
    edge            REAL NOT NULL,          -- model_prob - breakeven_prob
    expected_value  REAL NOT NULL,          -- model_prob * price - 1
    stake           REAL NOT NULL,
    rule_version    TEXT NOT NULL,
    -- written by the grader, after the fact
    settled_at      TEXT,
    outcome         TEXT,                   -- 'win' | 'lose' | 'void'
    pnl             REAL
);

CREATE INDEX idx_paper_bets_fixture ON paper_bets (fixture_id);
CREATE INDEX idx_paper_bets_settled ON paper_bets (settled_at);

-- Append-only. CLV is the primary metric (SPEC §5.1): did the price we took
-- beat the closing line? Measured against the DE-VIGGED close, because the
-- question is whether we were ahead of the market's final opinion, not whether
-- we beat a number inflated by margin.
CREATE TABLE clv_grades (
    grade_id        INTEGER PRIMARY KEY,
    bet_id          INTEGER NOT NULL REFERENCES paper_bets(bet_id),
    graded_at       TEXT NOT NULL DEFAULT (datetime('now')),
    bet_price       REAL NOT NULL,
    close_price     REAL NOT NULL,
    close_source    TEXT NOT NULL,          -- 'PSC' | 'AvgC' -- never mixed silently
    bet_prob        REAL NOT NULL,          -- de-vigged, at bet time
    close_prob      REAL NOT NULL,          -- de-vigged, at close
    clv             REAL NOT NULL,          -- close_prob - bet_prob; >0 = we were early
    clv_pct         REAL NOT NULL,          -- bet_price / close_price - 1
    UNIQUE (bet_id)
);

-- Append-only snapshot of what was live for a serving cycle. Without this,
-- "which model priced this bet, under which recalibration" is answerable only
-- by guessing from timestamps.
CREATE TABLE serving_state (
    state_id        INTEGER PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    cycle_label     TEXT NOT NULL,          -- e.g. '2026-08-15'
    model_version   TEXT NOT NULL,
    artifact_path   TEXT,
    fixtures_seen   INTEGER NOT NULL,
    predictions_written INTEGER NOT NULL,
    bets_written    INTEGER NOT NULL,
    rule_version    TEXT NOT NULL,
    notes           TEXT
);

-- Registry of frozen artifacts. The version string is derived from the
-- artifact's own contents (engine.serve.artifact), so a row here is a claim
-- that can be checked, not a label that has to be trusted.
CREATE TABLE model_runs (
    model_version   TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    fitted_at       TEXT NOT NULL,          -- training cutoff, not wall clock
    config_label    TEXT NOT NULL,
    n_train         INTEGER NOT NULL,
    n_teams         INTEGER NOT NULL,
    corpus_digest   TEXT NOT NULL,
    artifact_path   TEXT
);
