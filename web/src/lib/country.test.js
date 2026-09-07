// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ZONE_COUNTRY, DEFAULT_COUNTRY, countryFromLocale, detectCountry } from './country.js';

const known = new Set(['GB', 'KE', 'NG', 'GH', 'UG', 'ZA', 'US', 'IN', 'IE', 'DE', 'AU', 'BR']);

test('a representative dozen zones map to the country they are in', () => {
  const expected = {
    'Europe/London': 'GB',
    'Africa/Nairobi': 'KE',
    'Africa/Lagos': 'NG',
    'Africa/Accra': 'GH',
    'Africa/Kampala': 'UG',
    'Africa/Johannesburg': 'ZA',
    'America/New_York': 'US',
    'Asia/Kolkata': 'IN',
    'Europe/Dublin': 'IE',
    'Europe/Berlin': 'DE',
    'Australia/Sydney': 'AU',
    'America/Sao_Paulo': 'BR'
  };
  for (const [zone, country] of Object.entries(expected)) assert.equal(ZONE_COUNTRY[zone], country, zone);
});

test('the old names a browser may still report resolve through the links', () => {
  assert.equal(ZONE_COUNTRY['Asia/Calcutta'], 'IN');
  assert.equal(ZONE_COUNTRY['Europe/Kiev'], 'UA');
});

test('the locale region is read, and a bare language has none', () => {
  assert.equal(countryFromLocale('en-GB'), 'GB');
  assert.equal(countryFromLocale('sw-ke'), 'KE');
  assert.equal(countryFromLocale('zh-Hant-TW'), 'TW');
  assert.equal(countryFromLocale('en'), null);
  assert.equal(countryFromLocale(undefined), null);
});

test('the zone wins over the locale, and the locale over the default', () => {
  assert.equal(detectCountry('Africa/Nairobi', 'en-US', known), 'KE');
  assert.equal(detectCountry('Mars/Olympus', 'en-US', known), 'US');
  assert.equal(detectCountry('Mars/Olympus', 'fr', known), DEFAULT_COUNTRY);
  assert.equal(detectCountry(undefined, undefined, known), DEFAULT_COUNTRY);
});

test('a detected country the picker cannot show falls back to the default', () => {
  assert.equal(detectCountry('Europe/Kiev', 'en-GB', known), DEFAULT_COUNTRY);
  assert.equal(detectCountry('Europe/Kiev', 'en-GB', undefined), 'UA');
});
