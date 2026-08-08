-- 003: the tip list -- what the confidence rule published, and how it did.
-- Forward-only. Never edit an applied migration; add a new numbered one.

-- A tip is not a bet, and this table is not `paper_bets`. `paper_bets` records
-- a *value* decision: the model's probability beat the price's break-even.
-- A tip records a *confidence* decision, which ignores price entirely
-- (`engine/serve/tips.py`). The two rules select nearly disjoint fixtures --
-- value lives on longshots, confidence on favourites -- so they are separate
-- tables rather than one table with a rule column, and no query can average
-- across them by accident.
--
-- `UNIQUE (fixture_id, rule_version)` is the safety property, enforced here
-- rather than in Python: **one published tip per fixture per rule.** A tipster
-- that publishes two contradictory recommendations for the same match has no
-- defensible strike rate, and re-running a cycle at a lower threshold must not
-- be able to produce one. Changing the threshold means bumping rule_version.
CREATE TABLE tips (
    tip_id          INTEGER PRIMARY KEY,
    prediction_id   INTEGER NOT NULL REFERENCES predictions(prediction_id),
    fixture_id      INTEGER NOT NULL REFERENCES fixtures(fixture_id),
    published_at    TEXT NOT NULL DEFAULT (datetime('now')),
    side            TEXT NOT NULL CHECK (side IN ('H', 'D', 'A')),
    model_prob      REAL NOT NULL,
    threshold       REAL NOT NULL,
    -- Carried for reporting only. Neither column takes any part in selection;
    -- if either ever does, the product has become a value rule.
    best_price      REAL,
    avg_price       REAL,
    rule_version    TEXT NOT NULL,

    -- Written by the grader, after the fact. Both price levels are settled,
    -- not one: strike rate is what the product is sold on and return is what
    -- the customer gets, and the gap between them is the whole reason this
    -- table records more than a win flag.
    settled_at      TEXT,
    outcome         TEXT CHECK (outcome IN ('win', 'lose', 'void')),
    pnl_best        REAL,
    pnl_avg         REAL,

    UNIQUE (fixture_id, rule_version)
);

CREATE INDEX idx_tips_unsettled ON tips (settled_at) WHERE settled_at IS NULL;
CREATE INDEX idx_tips_fixture ON tips (fixture_id);
