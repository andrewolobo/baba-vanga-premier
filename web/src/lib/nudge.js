// The sign-up nudge (owner request 2026-09-24): a small card at the foot of
// the screen asking a signed-out visitor to sign up, shown once per session,
// a few seconds into their second page view -- never on the page they landed
// on, which is the pop-up Google's search guidance warns against.
//
// "Session" is sessionStorage: one tab, until it closes. A new tab is a new
// session and may show the card again.
//
// Pure: a function returning a Storage-shaped object comes in, so the rule is
// testable without a browser. A getter rather than the object because reading
// `window.sessionStorage` itself throws where storage is blocked.
export const VIEWS_KEY = 'bvp_nudge_views';
export const SHOWN_KEY = 'bvp_nudge_shown';
export const NUDGE_AFTER_VIEWS = 2;
export const NUDGE_DELAY_MS = 5000;

// Counts a page view; true when the card is due. Stays true on later views
// until `markShown`, so a card that never got to show (the visitor left
// before the delay ran out) is due again on the next page.
export const recordView = (getStorage) => {
  try {
    const storage = getStorage();
    if (storage.getItem(SHOWN_KEY) === '1') return false;
    const views = (Number(storage.getItem(VIEWS_KEY)) || 0) + 1;
    storage.setItem(VIEWS_KEY, String(views));
    return views >= NUDGE_AFTER_VIEWS;
  } catch {
    return false; // no storage, no way to keep it to once: never show
  }
};

export const markShown = (getStorage) => {
  try {
    getStorage().setItem(SHOWN_KEY, '1');
  } catch {
    // Unreachable in practice: recordView already needed storage to say yes.
  }
};
