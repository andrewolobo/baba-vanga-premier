// Which hero the front page renders (owner decision 2026-09-08): the
// pixel-video band (HeroVideo) or the parallax art it replaced (HeroClassic).
// Both components stay in the tree, so the revert is this one line:
// set VIDEO_HERO to false, rebuild, deploy — nothing else changes.
export const VIDEO_HERO = true;
