// Kick-off times, shown in the viewer's own zone.
//
// The API serves `match_date` and `kickoff_time` as **UK wall-clock** -- that
// is what both feeds publish (`services/fixture_sync.py` reads football-data's
// `Time`, `services/bbc_calendar.py` stores `displayTimeUK`) and what the
// grader keys fixtures on, so the wire format stays UK-local and the
// conversion happens here, once, at render. The browser knows the viewer's
// zone; the server does not.
//
// Europe/London is GMT in winter and BST in summer, and the switch dates are
// not fixed, so the offset is read from `Intl` for the instant in question
// rather than assumed.

const LONDON = 'Europe/London';

// Minutes Europe/London is ahead of UTC at instant `ms` (0 in GMT, 60 in BST).
function londonOffsetMinutes(ms) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: LONDON, hourCycle: 'h23',
    year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric'
  }).formatToParts(new Date(ms));
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  const wall = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'));
  return Math.round((wall - ms) / 60000);
}

// The instant a UK wall-clock `YYYY-MM-DD` + `HH:MM` denotes. Null when the
// time is missing or malformed -- a fixture the feed carried without one.
export function ukInstant(matchDate, kickoffTime) {
  if (!matchDate || !kickoffTime) return null;
  const [y, m, d] = matchDate.split('-').map(Number);
  const [hh, mm] = kickoffTime.split(':').map(Number);
  if ([y, m, d, hh, mm].some((n) => !Number.isFinite(n))) return null;
  const asIfUtc = Date.UTC(y, m - 1, d, hh, mm);
  // Guess with the offset at the UTC reading, then re-read at the corrected
  // instant: the two differ only when the guess itself crosses a DST switch.
  let instant = asIfUtc - londonOffsetMinutes(asIfUtc) * 60000;
  instant = asIfUtc - londonOffsetMinutes(instant) * 60000;
  return new Date(instant);
}

// `YYYY-MM-DD` of `instant` in `timeZone`.
function dateIn(instant, timeZone) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(instant);
  const get = (type) => parts.find((p) => p.type === type).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

// What to print for one fixture: `{ time, dayShift, zone }`.
//   time      "22:00" in the viewer's zone (24h, matching the rest of the page)
//   dayShift  0 when the local date is the UK date, +1 / -1 when it is not --
//             a 20:00 UK kick-off is 05:00 tomorrow in Sydney, and the list
//             is grouped by the UK date, so the row has to say so.
//   zone      the IANA zone used, for the footnote.
// Returns null when there is no time to show; the caller prints its dash.
export function localKickoff(matchDate, kickoffTime, timeZone) {
  const instant = ukInstant(matchDate, kickoffTime);
  if (!instant) return null;
  const zone = timeZone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  const time = new Intl.DateTimeFormat('en-GB', {
    timeZone: zone, hourCycle: 'h23', hour: '2-digit', minute: '2-digit'
  }).format(instant);
  const local = dateIn(instant, zone);
  const dayShift = local === matchDate ? 0 : (local > matchDate ? 1 : -1);
  return { time, dayShift, zone };
}

export function viewerZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
