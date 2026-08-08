-- 004: the tip list carries double chance.
-- Forward-only. Never edit an applied migration; add a new numbered one.
--
-- B8 ships the rule measured in `engine/eval/selection.py` (PRODUCT.md 3a):
-- recommend the outright favourite when it clears a floor, otherwise the
-- likeliest double chance that does not breach a ceiling. So `side` gains
-- '1X', 'X2' and '12', and the rule's two settings are stored per tip rather
-- than only the one.
--
-- SQLite cannot alter a CHECK constraint, so the table is rebuilt and copied.
-- Existing rows keep their values: `threshold` becomes `floor`, which is what
-- it always meant, and `ceiling` is null for tips published before the rule
-- had one.

CREATE TABLE tips_new (
    tip_id          INTEGER PRIMARY KEY,
    prediction_id   INTEGER NOT NULL REFERENCES predictions(prediction_id),
    fixture_id      INTEGER NOT NULL REFERENCES fixtures(fixture_id),
    published_at    TEXT NOT NULL DEFAULT (datetime('now')),
    side            TEXT NOT NULL CHECK (side IN ('H', 'D', 'A', '1X', 'X2', '12')),
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
       model_prob, threshold, NULL, best_price, avg_price,
       rule_version, settled_at, outcome, pnl_best, pnl_avg
FROM tips;

DROP TABLE tips;
ALTER TABLE tips_new RENAME TO tips;

CREATE INDEX idx_tips_unsettled ON tips (settled_at) WHERE settled_at IS NULL;
CREATE INDEX idx_tips_fixture ON tips (fixture_id);
