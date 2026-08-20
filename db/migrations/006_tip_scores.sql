-- 006: the score a tip was settled from.
-- Forward-only. Never edit an applied migration; add a new numbered one.

-- Written by the grader BESIDE `outcome`, in the same UPDATE -- 003's rule:
-- grading columns land beside the tip, never over it. Under v3 the score is
-- what settles a tip (`selection.won_from_score`, margin-aware), so the
-- record keeps the exact figures the outcome was derived from, and the site
-- can show a scoreline without `/tips/results` inventing one. `fixtures`
-- still carries no result (002's invariant is untouched). Rows settled before
-- this migration stay NULL until `scripts/backfill_tip_scores.py` re-reads
-- the pages that settled them; the API serves the NULL rather than a guess.
ALTER TABLE tips ADD COLUMN fthg INTEGER;
ALTER TABLE tips ADD COLUMN ftag INTEGER;
