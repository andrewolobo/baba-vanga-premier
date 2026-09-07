"""Google sign-in and the one-time phone capture (docs/AUTH_PLAN.md, B25).

The three write routes of the API and the two dependencies behind them,
against a real Postgres clone per test. Google is never called: the fixture
replaces `api.auth.verify_google_token` with a lookup over planted claims, so
"a valid credential" here is a key of CLAIMS and "an invalid one" is anything
else. What the token check itself does is google-auth's to guarantee; what
this module pins is everything the API does with the claims it returns.
"""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app, get_conn
from engine import config, db
from tests.test_api import _override

CLAIMS = {
    "alice": {"sub": "sub-alice", "email": "Alice@Example.com", "email_verified": True,
              "name": "Alice Anderson", "picture": "https://p/alice"},
    "alice-again": {"sub": "sub-alice", "email": "alice@example.com", "email_verified": True,
                    "name": "Alice B. Anderson", "picture": "https://p/alice2"},
    "bob": {"sub": "sub-bob", "email": "bob@example.com", "email_verified": False,
            "name": "Bob", "picture": None},
    "no-email": {"sub": "sub-nobody", "name": "Nobody"},
}

GB_PHONE = "07400 123456"          # +447400123456
KE_PHONE = "+254 712 345 678"      # +254712345678


def _verify(credential):
    try:
        return dict(CLAIMS[credential])
    except KeyError:
        raise ValueError("bad token") from None


@pytest.fixture
def auth_client(make_database, monkeypatch):
    """A migrated clone, Google stubbed out, the cookie not Secure (httpx's jar
    refuses a Secure cookie on http://testserver)."""
    url = make_database()
    conn = db.connect(url)
    db.migrate(conn)
    conn.commit()
    conn.close()
    monkeypatch.setattr(auth, "verify_google_token", _verify)
    monkeypatch.setattr(config, "COOKIE_SECURE", False)
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "test-client")
    app.dependency_overrides[get_conn] = _override(url)
    yield TestClient(app), url
    app.dependency_overrides.clear()


def sign_in(client, who="alice"):
    return client.post("/auth/google", json={"credential": who})


def query(url, sql, params=()):
    conn = db.connect(url)
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def execute(url, sql, params=()):
    conn = db.connect(url)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# --- sign-in ---------------------------------------------------------------


def test_sign_in_creates_a_user_a_session_and_a_cookie(auth_client):
    client, url = auth_client
    response = sign_in(client)
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["email"] == "alice@example.com", "stored lowercased"
    assert user["name"] == "Alice Anderson"
    assert user["phone_e164"] is None and user["phone_required"] is True

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{auth.COOKIE}=")
    for attribute in ("HttpOnly", "SameSite=lax", "Path=/", f"Max-Age={config.SESSION_DAYS * 86400}"):
        assert attribute in cookie, attribute
    assert "Secure" not in cookie

    token = client.cookies[auth.COOKIE]
    users = query(url, "SELECT google_sub, email, email_verified FROM users")
    assert users == [{"google_sub": "sub-alice", "email": "alice@example.com", "email_verified": True}]
    sessions = query(url, "SELECT token_hash, revoked_at, expires_at > now() AS live FROM user_sessions")
    assert len(sessions) == 1
    assert sessions[0]["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert sessions[0]["token_hash"] != token, "the store holds the hash, not the cookie"
    assert sessions[0]["revoked_at"] is None and sessions[0]["live"]


def test_the_cookie_is_secure_unless_a_development_machine_says_otherwise(auth_client, monkeypatch):
    client, _ = auth_client
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    assert "Secure" in sign_in(client).headers["set-cookie"]


def test_signing_in_again_is_the_same_user_with_a_second_session(auth_client):
    client, url = auth_client
    first = sign_in(client, "alice").json()["user"]
    execute(url, "UPDATE users SET last_login_at = now() - interval '1 day'")
    second = sign_in(client, "alice-again").json()["user"]
    assert second["user_id"] == first["user_id"]
    assert second["name"] == "Alice B. Anderson", "refreshed from the new token"
    assert query(url, "SELECT COUNT(*) AS n FROM users")[0]["n"] == 1
    assert query(url, "SELECT COUNT(*) AS n FROM user_sessions")[0]["n"] == 2
    assert query(url, "SELECT last_login_at > now() - interval '1 minute' AS moved FROM users")[0]["moved"]


def test_a_bad_credential_is_401_and_writes_nothing(auth_client):
    client, url = auth_client
    response = sign_in(client, "forged")
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert query(url, "SELECT COUNT(*) AS n FROM users")[0]["n"] == 0


def test_a_token_without_an_email_is_refused(auth_client):
    client, url = auth_client
    assert sign_in(client, "no-email").status_code == 401
    assert query(url, "SELECT COUNT(*) AS n FROM users")[0]["n"] == 0


def test_a_missing_credential_is_400(auth_client):
    client, _ = auth_client
    assert client.post("/auth/google", json={}).status_code == 400
    assert client.post("/auth/google", json={"credential": 42}).status_code == 400


def test_a_non_json_post_is_415(auth_client):
    client, _ = auth_client
    response = client.post("/auth/google", content="credential=alice",
                           headers={"content-type": "application/x-www-form-urlencoded"})
    assert response.status_code == 415


def test_a_cross_site_post_is_403(auth_client):
    client, url = auth_client
    response = client.post("/auth/google", json={"credential": "alice"},
                           headers={"sec-fetch-site": "cross-site"})
    assert response.status_code == 403
    assert query(url, "SELECT COUNT(*) AS n FROM users")[0]["n"] == 0


# --- /me -------------------------------------------------------------------


def test_me_is_anonymous_without_a_cookie(auth_client):
    client, _ = auth_client
    assert client.get("/me").json() == {"user": None}


def test_me_is_anonymous_with_a_forged_cookie(auth_client):
    client, _ = auth_client
    sign_in(client)
    client.cookies.set(auth.COOKIE, "not-the-token")
    assert client.get("/me").json() == {"user": None}


def test_me_reports_phone_required_until_the_phone_is_saved(auth_client):
    client, _ = auth_client
    sign_in(client)
    assert client.get("/me").json()["user"]["phone_required"] is True
    client.post("/me/phone", json={"phone": GB_PHONE, "country": "GB"})
    me = client.get("/me").json()["user"]
    assert me["phone_required"] is False and me["phone_e164"] == "+447400123456"


def test_an_expired_session_is_anonymous(auth_client):
    client, url = auth_client
    sign_in(client)
    execute(url, "UPDATE user_sessions SET expires_at = now() - interval '1 minute'")
    assert client.get("/me").json() == {"user": None}


def test_a_revoked_session_is_anonymous(auth_client):
    client, url = auth_client
    sign_in(client)
    execute(url, "UPDATE user_sessions SET revoked_at = now()")
    assert client.get("/me").json() == {"user": None}


def test_the_sliding_refresh_is_written_at_most_once_a_day(auth_client):
    client, url = auth_client
    sign_in(client)
    execute(url, "UPDATE user_sessions SET last_seen_at = now() - interval '2 days',"
                 " expires_at = now() + interval '1 day'")
    assert client.get("/me").json()["user"] is not None
    first = query(url, "SELECT expires_at, last_seen_at,"
                       " expires_at > now() + interval '29 days' AS extended FROM user_sessions")[0]
    assert first["extended"], "a stale session is extended on use"
    assert client.get("/me").json()["user"] is not None
    second = query(url, "SELECT expires_at, last_seen_at FROM user_sessions")[0]
    assert second == {"expires_at": first["expires_at"], "last_seen_at": first["last_seen_at"]}, \
        "a session seen today is not written again"


# --- /me/phone -------------------------------------------------------------


def test_the_phone_is_normalised_to_e164(auth_client):
    client, url = auth_client
    sign_in(client)
    response = client.post("/me/phone", json={"phone": GB_PHONE, "country": "gb"})
    assert response.status_code == 200
    assert response.json()["user"]["phone_e164"] == "+447400123456"
    assert response.json()["user"]["phone_required"] is False
    row = query(url, "SELECT phone_e164, phone_country, phone_captured_at IS NOT NULL AS stamped,"
                     " phone_verified_at FROM users")[0]
    assert row == {"phone_e164": "+447400123456", "phone_country": "GB", "stamped": True,
                   "phone_verified_at": None}


def test_a_typed_prefix_wins_over_the_picked_country(auth_client):
    client, url = auth_client
    sign_in(client)
    assert client.post("/me/phone", json={"phone": KE_PHONE, "country": "GB"}).status_code == 200
    assert query(url, "SELECT phone_e164, phone_country FROM users")[0] == \
        {"phone_e164": "+254712345678", "phone_country": "KE"}


@pytest.mark.parametrize("phone", ["123", "07400 12345", "abc", ""])
def test_an_invalid_phone_is_400(auth_client, phone):
    client, url = auth_client
    sign_in(client)
    assert client.post("/me/phone", json={"phone": phone, "country": "GB"}).status_code == 400
    assert query(url, "SELECT phone_e164 FROM users")[0]["phone_e164"] is None


def test_the_phone_is_captured_once(auth_client):
    client, url = auth_client
    sign_in(client)
    assert client.post("/me/phone", json={"phone": GB_PHONE, "country": "GB"}).status_code == 200
    response = client.post("/me/phone", json={"phone": KE_PHONE, "country": "KE"})
    assert response.status_code == 409
    assert query(url, "SELECT phone_e164 FROM users")[0]["phone_e164"] == "+447400123456"


def test_a_phone_on_another_account_is_409(auth_client):
    client, url = auth_client
    sign_in(client, "alice")
    assert client.post("/me/phone", json={"phone": GB_PHONE, "country": "GB"}).status_code == 200
    client.cookies.clear()
    sign_in(client, "bob")
    response = client.post("/me/phone", json={"phone": GB_PHONE, "country": "GB"})
    assert response.status_code == 409
    assert "another account" in response.json()["detail"]
    assert query(url, "SELECT phone_e164 FROM users WHERE google_sub = 'sub-bob'")[0]["phone_e164"] is None
    # The connection is autocommit, so the refused statement leaves it usable.
    assert client.get("/me").json()["user"]["email"] == "bob@example.com"


def test_saving_a_phone_needs_a_session(auth_client):
    client, _ = auth_client
    assert client.post("/me/phone", json={"phone": GB_PHONE, "country": "GB"}).status_code == 401


# --- logout ----------------------------------------------------------------


def test_logout_revokes_the_session_and_clears_the_cookie(auth_client):
    client, url = auth_client
    sign_in(client)
    response = client.post("/auth/logout", json={})
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert query(url, "SELECT revoked_at IS NOT NULL AS revoked FROM user_sessions")[0]["revoked"]
    assert client.get("/me").json() == {"user": None}


def test_logout_without_a_session_is_still_204(auth_client):
    client, _ = auth_client
    assert client.post("/auth/logout", json={}).status_code == 204


# --- /auth/config and the primitives ----------------------------------------


def test_auth_config_serves_the_client_id_and_the_regions(auth_client):
    client, _ = auth_client
    body = client.get("/auth/config").json()
    assert body["google_client_id"] == "test-client"
    assert {"code": "GB", "dial": 44} in body["regions"]
    assert {"code": "KE", "dial": 254} in body["regions"]
    assert body["regions"] == sorted(body["regions"], key=lambda r: r["code"])


def test_normalise_phone():
    assert auth.normalise_phone("07400 123456", "GB") == ("+447400123456", "GB")
    assert auth.normalise_phone("0712 345 678", "KE") == ("+254712345678", "KE")
    assert auth.normalise_phone("+254712345678", "GB") == ("+254712345678", "KE")
    for raw, country in [("123", "GB"), ("abc", "GB"), ("07400 123456", ""), ("", "GB")]:
        with pytest.raises(ValueError):
            auth.normalise_phone(raw, country)


def test_hash_token_is_sha256_and_tokens_are_fresh():
    token = auth.new_token()
    assert len(token) >= 43, "256 bits, URL-safe"
    assert auth.hash_token(token) == hashlib.sha256(token.encode()).hexdigest()
    assert auth.new_token() != token


def test_the_verifier_fails_closed_without_a_client_id(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    with pytest.raises(ValueError):
        auth.verify_google_token("anything")
