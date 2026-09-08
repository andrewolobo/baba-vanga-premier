-- 003: betPawa's ids behind the site's wager buttons (docs/BETPAWA_PLAN.md).
-- Forward-only. Never edit an applied migration; add a new numbered one.
--
-- Written by the cycle's `betpawa` step (services/betpawa_feed.py), read by
-- the API. One row per fixture the bookmaker lists: its event id, and one
-- row per side the rule can publish with the selection id whose prefill URL
-- opens that wager (BETPAWA_PLAN.md 1.3). Ids are TEXT because that is how
-- the API writes them and nothing here does arithmetic on one; they are the
-- same on every betPawa country site (1.4), so there is no per-brand row.
--
-- `odds` is stored because it arrives with the id, not because anything
-- shows it: the site publishes no prices (STATE.md), and a morning's odds
-- are stale by kick-off. It is the operator's evidence that the selection
-- was the one intended, nothing more. UTC-text timestamps, the baseline's
-- convention for cycle-written tables (POSTGRES_PLAN.md D3).
--
-- Selections are replaced per fixture on every run, so a line the book
-- withdraws disappears from here at the next scrape rather than lingering
-- as a link to nothing. A fixture with no row is simply one the button does
-- not render for.
CREATE TABLE betpawa_events (
    fixture_id      INTEGER PRIMARY KEY REFERENCES fixtures(fixture_id),
    event_id        TEXT NOT NULL UNIQUE,
    competition_id  TEXT NOT NULL,
    start_time      TEXT NOT NULL,       -- UTC, as published ('2026-09-08T18:45:00Z')
    fetched_at      TEXT NOT NULL
                    DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE betpawa_selections (
    fixture_id      INTEGER NOT NULL REFERENCES betpawa_events(fixture_id) ON DELETE CASCADE,
    side            TEXT NOT NULL CHECK (side IN ('H', 'D', 'A', '1X', 'X2', '12',
                                                  'H+1.5', 'A+1.5')),
    selection_id    TEXT NOT NULL,
    odds            DOUBLE PRECISION,
    PRIMARY KEY (fixture_id, side)
);
