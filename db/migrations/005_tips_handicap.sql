-- 005: the tip list carries the +1.5 handicap (confidence-v3, BACKLOG.md B21).
-- Forward-only. Never edit an applied migration; add a new numbered one.
--
-- B21 measured the underdog +1.5 as a fallback candidate at +5.37 paired
-- points of strike over v2 (gate row 110), and the owner adopted it
-- (V3_ADOPTION_PLAN.md). `side` gains the two concrete handicap codes:
-- 'H+1.5' (home gets the 1.5-goal start) and 'A+1.5'. Concrete rather than
-- the eval code's fav-relative 'D+1.5', so a tip settles from side + final
-- score alone (plan decision D1). Half line: no push, no void.
--
-- SQLite cannot alter a CHECK constraint, so the table is rebuilt and copied,
-- exactly as 004 did. Existing rows are untouched; v2 never emitted these
-- sides, which is also what makes rolling the code back safe -- the widened
-- CHECK accepts everything v2 writes.

CREATE TABLE tips_new (
    tip_id          INTEGER PRIMARY KEY,
    prediction_id   INTEGER NOT NULL REFERENCES predictions(prediction_id),
    fixture_id      INTEGER NOT NULL REFERENCES fixtures(fixture_id),
    published_at    TEXT NOT NULL DEFAULT (datetime('now')),
    side            TEXT NOT NULL CHECK (side IN ('H', 'D', 'A', '1X', 'X2', '12',
                                                  'H+1.5', 'A+1.5')),
    model_prob      REAL NOT NULL,
    floor           REAL NOT NULL,
    ceiling         REAL,
    best_price      REAL,
    avg_price       REAL,
    rule_version    TEXT NOT NULL,
    settled_at      TEXT,
    outcome         TEXT CHECK (outcome IN ('win', 'lose', 'void')),
    pnl_best        REAL,
    pnl_avg         REAL,
    UNIQUE (fixture_id, rule_version)
);

INSERT INTO tips_new (tip_id, prediction_id, fixture_id, published_at, side,
                      model_prob, floor, ceiling, best_price, avg_price,
                      rule_version, settled_at, outcome, pnl_best, pnl_avg)
SELECT tip_id, prediction_id, fixture_id, published_at, side,
       model_prob, floor, ceiling, best_price, avg_price,
       rule_version, settled_at, outcome, pnl_best, pnl_avg
FROM tips;

DROP TABLE tips;
ALTER TABLE tips_new RENAME TO tips;

CREATE INDEX idx_tips_unsettled ON tips (settled_at) WHERE settled_at IS NULL;
CREATE INDEX idx_tips_fixture ON tips (fixture_id);
