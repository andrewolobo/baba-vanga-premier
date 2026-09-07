"""Sign-in primitives for `api.main`: Google token verification, session
tokens, phone normalisation (docs/AUTH_PLAN.md, B25).

No SQL here -- the endpoints own their queries. What lives here is the set
of seams a test replaces: `verify_google_token` is monkeypatched so the
suite never talks to Google, and the rest is pure.
"""

from __future__ import annotations

import hashlib
import secrets

import phonenumbers
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from engine import config

#: The session cookie. Its value is `new_token()`; the store holds `hash_token()`.
COOKIE = "bvp_session"


def verify_google_token(credential: str) -> dict:
    """Claims of a Google ID token, or ValueError.

    google-auth checks the signature against Google's published certificates,
    `aud` against BVP_GOOGLE_CLIENT_ID, `iss` and `exp`. One HTTPS fetch of the
    certificates per call: this runs once per sign-in, never per request, so it
    is not cached. An unset client id fails closed rather than accepting any
    audience.
    """
    if not config.GOOGLE_CLIENT_ID:
        raise ValueError("BVP_GOOGLE_CLIENT_ID is not set")
    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), config.GOOGLE_CLIENT_ID,
        clock_skew_in_seconds=10)


def new_token() -> str:
    """256 random bits, URL-safe: the cookie value."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """What `user_sessions.token_hash` holds. SHA-256, unsalted: the input is
    256 random bits, so there is nothing for a rainbow table to find."""
    return hashlib.sha256(token.encode()).hexdigest()


def normalise_phone(raw: str, country: str) -> tuple[str, str]:
    """(E.164, region) or ValueError. `country` is the region the user picked;
    a number typed with its own '+' prefix overrides it."""
    try:
        number = phonenumbers.parse(raw, country or None)
    except phonenumbers.NumberParseException as error:
        raise ValueError("not a phone number") from error
    if not phonenumbers.is_valid_number(number):
        raise ValueError("not a valid phone number for that country")
    return (phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
            phonenumbers.region_code_for_number(number))


def regions() -> list[dict]:
    """[{code, dial}] for every region phonenumbers knows -- the country
    picker's data, so the browser carries no country table of its own."""
    return sorted(({"code": r, "dial": phonenumbers.country_code_for_region(r)}
                   for r in phonenumbers.SUPPORTED_REGIONS), key=lambda d: d["code"])
