# Match analysis samples — prompt v1, 2026-10-10

Five real fixtures from the production copy (`bvp_prod`), written by `gpt-6-sol` through the full chain and passed by the validator. Nothing is stored or shown on the site. Generated with `python -m services.analysis analyse`. Delete this file when reviewed.

## Bournemouth v Liverpool — Premier League, 2026-09-20

**Published call:** Either team to win (76.9%) · flags: small_sample (home), small_sample (away) · tokens 8533 in / 1128 out · attempts 3

**Preview.** Bournemouth host Liverpool with both sides finding draws easier to come by than wins in the early Premier League season. Bournemouth have drawn three of their four league matches and remain without a win; both home games have finished level. They have scored in every league match, but have yet to keep a clean sheet. Liverpool are unbeaten, with a win and three draws. Their away results include a win and a draw, and they have scored 2.0 goals per away game. That record gives Liverpool the stronger start, while Bournemouth's scoring leaves a home win possible. None of the last five meetings ended level, including Bournemouth's 3-2 home win in January, though past meetings do not settle this one. The published call is either team to win, meaning a draw would defeat it. The model rates that outcome at 76.9%: Liverpool's outright-win estimate did not reach the rule's floor, and this was the highest-probability eligible fallback below its ceiling.

**Why this call.** Liverpool's 45.4% outright-win estimate falls below the 55.0% floor, so the rule moves to fallback markets. Either team to win, at 76.9%, is the most probable eligible fallback within the 85.0% ceiling. Liverpool's unbeaten start and the absence of draws in the last five meetings support it, but both clubs' frequent draws this season are a substantial counterpoint. This is not a call that Liverpool must win.

Supporting: `MENU_A, MENU_12, AWAY_LOST_SEASON, AWAY_WON_VENUE, H2H_DRAWS_L5, H2H_MATCH_1`  
Against: `HOME_DRAWN_SEASON, HOME_FORM_VENUE, AWAY_DRAWN_SEASON, AWAY_DRAWN_VENUE, MENU_D`

**Risks.** The small-sample flag applies to both teams: each has played only four league games this season, so their current records may not be representative. Draws are the clearest danger to the call, particularly after Bournemouth drew both home games and Liverpool drew three of their four league matches.

**Bournemouth profile** (trend: stable). Bournemouth have drawn 3 of their 4 league games this season, losing the other and remaining without a win. Their results have therefore yielded 0.75 points per game. They have scored 1.5 goals per game but conceded 1.75, and have yet to keep a clean sheet. Both teams have scored in 100% of their league matches. At home, Bournemouth have drawn both games, scoring and conceding 1.5 goals per game. Those home results show resilience, but the lack of a league win and the absence of clean sheets limit the strength of their overall record.

Strengths: Drawn both home league games; Scoring 1.5 goals per game this season. Weaknesses: No league wins this season; No clean sheets this season; Conceding 1.75 goals per game this season.

**Liverpool profile** (trend: stable). Liverpool are unbeaten in their league games this season, with one win and three draws across four matches. Their away record comprises a draw and a win from two games, producing 2.0 points per game. They have scored 2.0 goals per away game and conceded 1.0, although the away sample remains small. Across all league games, their scoring rate is 1.5 goals per game, and they have kept clean sheets in 50% of matches. Draws have been the main constraint on their overall results. There is no last-five-game window for a meaningful form comparison.

Strengths: Unbeaten in league games this season; 2.0 goals scored per away game; Clean sheets in 50% of league games. Weaknesses: Three draws in four league games; Away figures cover only two matches.

## West Ham United v Queens Park Rangers — Championship, 2026-10-09

**Published call:** West Ham United win (70.1%) · flags: results_gap (home), new_to_division (home), results_gap (away) · tokens 11088 in / 1692 out · attempts 4

**Preview.** West Ham United host Queens Park Rangers with the stronger recent results. West Ham have won four of their last five Championship games and drawn the other, scoring 3.6 goals per game across that spell. Their home record also supports the published West Ham win call: three wins in four league matches, with 3.5 goals scored per game. QPR have shown resilience, losing only once in their last five, but have won only once and arrive after three successive draws. Those draws are a reason for caution rather than evidence that an away win is more likely. West Ham have also drawn their latest league match and have already lost at home this season. The model puts a West Ham win at 70.1%, above the rule’s 55% floor, so the rule selects the outright win without turning to a fallback. Older meetings offer limited context: West Ham won two and drew two, but those matches were played between 2012 and 2015.

**Why this call.** West Ham’s four wins in their last five league games and three wins in four at home underpin the published outright call. Their recent scoring adds to that case, while QPR have won only once in their last five. The outright win clears the rule’s 55% floor, so the rule selects it rather than an eligible fallback.

Supporting: `MENU_H, HOME_WON_L5, HOME_WON_VENUE, HOME_GF_PG_L5, AWAY_WON_L5, H2H_HOME_WINS_L5`  
Against: `HOME_DRAWN_L5, HOME_LOST_VENUE, AWAY_DRAWN_L5, AWAY_LOST_L5, H2H_DRAWS_L5`

**Risks.** Results are missing from both teams’ records, so some season figures are left out and the available form may not tell the full story. West Ham were relegated from the Premier League, so last season’s level may not carry over to this division. QPR’s recent draws and West Ham’s home defeat also leave room for a result other than the published call.

**West Ham United profile** (trend: stable). West Ham United have won four of their last five league games and drawn the other, taking 2.6 points per game across that spell. Their attacking output has been strong at 3.6 goals per game, although they have also conceded 1.2 per game. At home this season, they have won three of four league matches and lost one. Their home scoring rate stands at 3.5 goals per game, while half of those matches have ended with a clean sheet. All four home games have featured three or more goals. No longer overall results window is available to establish a trend against their recent form.

Strengths: Four wins in the last five league games; 3.6 goals scored per game in the last five; Three wins in four home league games. Weaknesses: 1.2 goals conceded per game in the last five; One defeat in four home league games.

**Queens Park Rangers profile** (trend: stable). Queens Park Rangers have taken 1.2 points per game across their last 5 league matches, with 1 win, 3 draws and 1 defeat. Their most recent 3 results were draws, suggesting a run of close outcomes without a win. They have scored and conceded 1.0 goals per game in this period, while keeping clean sheets in 20% of matches. Both teams scored in 60% of those games, and 40% featured three or more goals. The recent results show some resilience, but the single win limits the strength of their form. No longer-window results are provided for a trend comparison.

Strengths: 3 draws in the last 5 league matches; Only 1 defeat in that period. Weaknesses: Only 1 win in the last 5 league matches; Clean sheets in 20% of recent matches.

## Burton Albion v Huddersfield Town — League One, 2026-10-03

**Published call:** Burton Albion Home +1.5 (79.2%) · flags: results_gap (home), results_gap (away) · tokens 6805 in / 1220 out · attempts 3

**Preview.** Burton Albion host Huddersfield Town in League One on 3 October with the published call on Burton Albion Home +1.5. It comes in if Burton avoid defeat by two or more goals; it does not require them to win. Burton have won twice and drawn twice in their last five league games, scoring 1.8 goals per game. Their recent meetings with Huddersfield also offer encouragement: Burton won the two most recent home meetings, while the other recent meetings listed ended in draws or a Burton win.

Huddersfield remain a threat. They have matched Burton’s recent return of two wins and two draws, and have conceded 1.0 goal per game across their last five. Their away record is less imposing, though, with one win, two draws and one defeat. The model makes Huddersfield the outright favourite at 43.5%, below the rule’s 55% floor. Among eligible fallbacks beneath the 85% ceiling, Burton +1.5 has the highest model probability, at 79.2%.

**Why this call.** The call allows for a narrow Huddersfield win while backing Burton to avoid a heavier defeat. Burton’s recent scoring and favourable meetings support that margin, though their 1.6 goals conceded per game recently is a concern. Huddersfield’s outright win probability misses the rule’s floor; Burton +1.5 is the most probable eligible fallback below its ceiling.

Supporting: `HOME_WON_L5, HOME_DRAWN_L5, HOME_GF_PG_L5, H2H_MATCH_1, H2H_MATCH_3, AWAY_FORM_VENUE, MENU_A, MENU_H15`  
Against: `HOME_GA_PG_L5, HOME_CS_PCT_L5, AWAY_WON_L5, AWAY_GA_PG_L5, MENU_A`

**Risks.** The results_gap flag applies to both teams: a result is missing from each record, so some season figures are left out. That limits how fully the available form describes either side. Burton’s recent concession rate is the clearest on-field risk to the call.

**Burton Albion profile** (trend: stable). Burton Albion’s recent league form has been mixed but generally competitive. Across their last 5 games, they recorded 2 wins, 2 draws and 1 defeat, averaging 1.6 points per game. They scored 1.8 goals per game but also conceded 1.6, suggesting that defensive solidity has not matched their attacking output. Both sides scored in 60% of those matches, while 80% featured three or more goals. Clean sheets came in 20% of games. These figures describe a side that has usually found goals recently, though it has also allowed opponents opportunities. No longer comparison window is provided to assess a change in form.

Strengths: 2 wins and 2 draws in the last 5 games; 1.8 goals scored per game recently. Weaknesses: 1.6 goals conceded per game recently; Clean sheets in 20% of recent games.

**Huddersfield Town profile** (trend: stable). Huddersfield Town have taken 1.6 points per game across their last 5 league matches, with 2 wins, 2 draws and 1 defeat. They have scored 1.4 goals per game and conceded 1.0 in that stretch, although both sides scored in 80% of those matches. Their away record this season is more restrained: 1 win, 2 draws and 1 defeat, with 1.25 points per game. Away from home, they have scored and conceded 1.0 goals per game, while both sides scored in 75% of matches. The available figures show a competitive recent spell, but do not establish a longer-term trend.

Strengths: 2 wins in the last 5 league matches; 1.0 goals conceded per game in the last 5; 1 away defeat this season. Weaknesses: 1.25 points per game away from home; 25% clean sheets away from home; Both sides scored in 80% of the last 5 matches.

## Reading v Bradford City — League One, 2026-10-03

**Published call:** Bradford City Away +1.5 (80.0%) · flags: results_gap (home), results_gap (away) · tokens 6498 in / 1193 out · attempts 3

**Preview.** Reading host Bradford City with strong recent attacking form: they have won 3 of their last 5 league games and scored 2.6 goals per game. That makes a convincing home win a genuine threat to the published Bradford City +1.5 call. Bradford’s away record points the other way. They have won 3 of their 4 away league games, conceded 0.5 goals per game on those trips and kept clean sheets in 75%. They have also won their last 3 league games, though their recent scoring rate is only 0.8 goals per game.

The call requires Bradford to avoid losing by 2 or more goals, not to win the match. The model puts a Reading win at 42.7%, below the rule’s 55% floor, so the outright home win was not selected. Bradford +1.5 is the most probable eligible fallback within the 85% ceiling, at 80.0%. The available season record has missing results for both clubs, limiting how firmly their figures can be read.

**Why this call.** Bradford’s away defending supports a call that can still succeed if Reading win narrowly: they have conceded 0.5 goals per away game and kept clean sheets in 75% of those matches. Reading’s outright-win probability of 42.7% falls below the 55% floor. Of the eligible fallbacks, Bradford +1.5 has the highest model probability within the 85% ceiling, at 80.0%.

Supporting: `AWAY_WON_VENUE, AWAY_GA_PG_VENUE, AWAY_CS_PCT_VENUE, AWAY_FORM_L5, H2H_MATCH_1, MENU_H, MENU_A15`  
Against: `HOME_WON_L5, HOME_GF_PG_L5, HOME_O25_PCT_L5, AWAY_GF_PG_VENUE, AWAY_LOST_L5`

**Risks.** The results_gap flag applies to both Reading and Bradford City: a result is missing from each record, so some season figures are left out. Reading’s recent scoring rate is the clearest match-related threat to Bradford avoiding a defeat by 2 or more goals.

**Reading profile** (trend: stable). Reading have won 3 of their last 5 league games, drawing 1 and losing 1, for 2.0 points per game. Their attacking return has been 2.6 goals per game, while they have conceded 1.0 per game. Clean sheets in 40% of those matches indicate some defensive resilience, although both teams scored in 60%. Matches with three or more goals accounted for 80%, reflecting a run in which goals have been a regular feature. The available facts cover only the last 5 league games, so there is no longer window against which to assess whether their form is improving or declining.

Strengths: 3 wins in the last 5 league games; 2.6 goals scored per game; Clean sheets in 40% of games. Weaknesses: Both teams scored in 60% of games; 1.0 goal conceded per game.

**Bradford City profile** (trend: stable). Bradford City have won 3 of their last 5 league games, with the results sequence showing those wins came after 2 defeats. That run has produced 1.8 points per game. Their recent scoring rate is 0.8 goals per game, while they have also conceded 0.8 per game. Away from home this season, they have won 3 of 4 league matches and taken 2.25 points per game. Their away defensive record is notable: they have conceded 0.5 goals per game and kept clean sheets in 75% of those matches. Away scoring remains modest at 0.75 goals per game.

Strengths: 3 wins in the last 5 league games; 3 wins in 4 away league games; Clean sheets in 75% of away league games. Weaknesses: 0.8 goals scored per game in the last 5; 0.75 goals scored per away game; 2 defeats in the last 5 league games.

## Brighton & Hove Albion v Arsenal — Premier League, 2026-09-19

**Published call:** Arsenal or draw (76.5%) · flags: small_sample (home), small_sample (away) · tokens 8897 in / 1176 out · attempts 3

**Preview.** Arsenal visit Brighton & Hove Albion after winning all four of their Premier League games this season. They have conceded 0.25 goals per game overall and won both away fixtures without conceding. Brighton also bring strong early form: they are unbeaten in two home games, scoring 2.5 goals per game there, and have won two of their four league matches overall. That makes a Brighton win a credible threat rather than something to dismiss. Recent meetings nevertheless favour the published Arsenal-or-draw call: Arsenal won three of the last five, with the other two ending level. The model gives Arsenal an outright-win probability of 51.1%, below the rule’s 55% floor. It therefore turns to eligible fallback markets, where Arsenal or draw has the highest probability at 76.5%, within the 85% ceiling. The selection covers a draw as well as an Arsenal win; it is not a prediction that a draw is more likely than an Arsenal victory.

**Why this call.** Arsenal’s perfect league start, away wins without conceding and unbeaten record across the last five meetings support Arsenal or draw. Their outright-win probability of 51.1% misses the 55% floor, so the rule selects the most probable eligible fallback: X2 at 76.5%. Brighton’s unbeaten home start and strong scoring record remain the main counterarguments.

Supporting: `AWAY_WON_SEASON, AWAY_WON_VENUE, AWAY_GA_PG_VENUE, H2H_HOME_WINS_L5, H2H_DRAWS_L5, H2H_AWAY_WINS_L5, MENU_A, MENU_X2, MENU_12`  
Against: `HOME_LOST_VENUE, HOME_GF_PG_VENUE, HOME_WON_SEASON, MENU_H`

**Risks.** The small_sample flags apply to both teams: each has played only four league games this season, with just two games at the relevant venue. Their promising early records may therefore be less reliable than they appear. Brighton’s unbeaten home record and scoring rate are the clearest threats to Arsenal or draw.

**Brighton & Hove Albion profile** (trend: stable). Brighton & Hove Albion have won two of their four league games this season, drawing one and losing one. They have scored 3.25 goals per game while conceding 1.25, with three or more goals scored in 75% of their matches. Their home record is unbeaten after two games: one win and one draw. At home, they have scored 2.5 goals per game and conceded 0.5, though the venue sample remains small. With no last-five-game window available to compare against a longer period, there is insufficient evidence to identify a clear direction in form.

Strengths: Unbeaten in two home league games; Scoring 3.25 goals per game overall; Conceding 0.5 goals per game at home. Weaknesses: One defeat in four league games; Conceding 1.25 goals per game overall; Home record covers only two games.

**Arsenal profile** (trend: stable). Arsenal have won all 4 of their league games this season, averaging 2.0 goals scored and 0.25 conceded per game. Their away record is also strong: they have won both away games, scoring 1.5 goals per game without conceding. Both away matches ended with fewer than three goals, compared with 50% of their league games overall. The defensive record is a clear strength, although the away figures come from only 2 matches. With no last-five-game window available for comparison, there is not enough evidence to identify a change in form.

Strengths: Wins in all 4 league games; No goals conceded in 2 away games; 75% clean-sheet rate across league games. Weaknesses: Away record covers only 2 games; Lower scoring rate away than overall.
