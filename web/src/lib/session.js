// The account calls (docs/AUTH_PLAN.md, B25): the three writes the API has,
// the two reads that go with them, and the pure helpers the layout renders
// from. The session itself is an HttpOnly cookie the browser carries on
// every same-origin request; nothing here stores a token, and nothing here
// decides who is signed in -- `getMe` asks the server, which is the only
// place that knows.
import { get, post } from './api.js';

export const getAuthConfig = () => get('/auth/config');
export const getMe = async () => (await get('/me')).user;
export const signInWithGoogle = async (credential) =>
  (await post('/auth/google', { credential })).user;
export const savePhone = async (phone, country) =>
  (await post('/me/phone', { phone, country })).user;
export const signOut = () => post('/auth/logout', {});

// The phone gate: a signed-in user who has not given a number yet.
export const phoneRequired = (user) => !!user && user.phone_required === true;

// What the header calls someone: the first word of their name, or the part
// of the email before the @ when Google sent no name.
export const firstName = (user) =>
  String(user?.name || user?.email || '')
    .split(/[\s@]/)[0];

// Enables the Save button, nothing more. Six or more digits with the
// punctuation a phone number is typed with; the server's `phonenumbers`
// verdict is the one the form shows.
export const plausiblePhone = (raw) => {
  const s = String(raw ?? '').trim();
  return /^\+?[\d\s().-]{6,20}$/.test(s) && s.replace(/\D/g, '').length >= 6;
};
