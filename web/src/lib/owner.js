// Owner-only detail on a public page -- the rule version and its parameters.
//
// This is obscurity, not security: anyone told the parameter can flip it, and
// `rule_version` still rides on the wire. It is sized for the job it does,
// which is keeping the rule's name out of testers' sight. If the wire ever has
// to be clean too, that is a server-side change layered on top of this one.
//
//   /?owner=1   show, and remember it in this browser
//   /?owner=0   hide, and forget
//
// Pure: the URL search string and a Storage-shaped object come in, so the
// decision is testable without a browser.
export const KEY = 'bvp_owner';

export const resolveOwner = (search, storage) => {
  try {
    const flag = new URLSearchParams(search).get('owner');
    if (flag === '1') storage.setItem(KEY, '1');
    else if (flag === '0') storage.removeItem(KEY);
    return storage.getItem(KEY) === '1';
  } catch {
    return false; // storage unavailable (private mode, blocked): public view
  }
};
