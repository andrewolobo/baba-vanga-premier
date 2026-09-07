# AUTH_PLAN — Google sign-in with one-time phone capture (B25)

Written **2026-09-07**, before anything was built. Owner request: add Google
authentication for user sign-in; capture a phone number **once** at the end
of authentication; certain features will later sit behind sign-in (out of
scope now, but the design must leave hooks). This file is the plan; nothing
in it has run. No rule, cycle, grading or ledger change — 0 configurations.

Reading order for a thread picking this up: `STATE.md` → this file →
`BACKLOG.md` B25 → `POSTGRES_PLAN.md` §1 (why the store moved, and what it
decided for these tables) → `api/main.py` (`get_conn`, the endpoint style)
→ `web/src/routes/+layout.svelte` (where the control and the gate go).

Owner decisions taken 2026-09-07, before this was written:
- **DB-backed session** with an opaque HttpOnly cookie, not a JWT.
- **Phone mandatory**, stored E.164, **format-validated only** — SMS
  verification is a later item (`docs/notes`). Default country **detected**,
  not hard-coded.
- **The domain is attached to the site.** TLS is a *verify* step here, not
  a build step (`DEPLOY.md` step 5b's "blocked: no domain" is stale).

---

## 0. What is being built, in one paragraph

The SPA loads Google Identity Services, renders Google's button in the
header, and posts the resulting ID token to a new `POST /auth/google`.
FastAPI verifies it with `google-auth` (signature, `aud`, `iss`, `exp`),
upserts a `users` row on `google_sub`, inserts a `user_sessions` row holding
the SHA-256 of a random 256-bit token, and sets that token as an
`HttpOnly; SameSite=Lax; Secure` cookie. Every later request resolves the
cookie through a `current_user` dependency: one SELECT and, at most once a
day per session, one UPDATE (sliding 30-day expiry). `GET /me` reports the
user and a `phone_required` flag; the layout blocks the site with a phone
modal until `POST /me/phone` succeeds, which the server validates and
normalises to E.164 with `phonenumbers` and writes **exactly once**
(`UPDATE … WHERE phone_e164 IS NULL`; zero rows → 409). The default country
for the phone field is detected client-side from the browser's time zone,
with the locale's region as fallback, and the user can change it. **Nothing
is gated yet**; `require_user` exists because `/me/phone` needs it, and the
`/parlay` gate is a documented three-line change (§10).

## 1. What exists, and what collides

Verified against the tree at `8342fd8` (2026-09-07).

- **The store moved to Postgres for this feature** (`POSTGRES_PLAN.md`,
  live in production 2026-09-04) and already decided the shape: psycopg 3,
  raw SQL, no ORM, the existing `.sql` runner, and **`002_users.sql`** as
  the next migration (§6 there reserves the name). Its §1.2 blesses
  `timestamptz`/`boolean` "for the tables that do not exist yet".
- **The API is documented and tested as read-only.**
  `tests/test_api.py::test_the_api_exposes_no_write_routes` asserts the
  route table's methods are ⊆ {GET, HEAD, OPTIONS}; the module docstring of
  `api/main.py` says "a request can never change what was served". A POST
  breaks the test; the amendment is deliberate and recorded (§4).
- **`get_conn` is autocommit** (one connection per request, pinned by
  `test_the_request_connection_is_opened_autocommit`). It stays so; the one
  multi-statement write wraps itself in `with conn.transaction():`.
- **CORS** allows GET only from the Vite origins and no credentials. It
  **stays as is**: the SPA is same-origin in both environments (Vite proxy
  in development, nginx `location /api/` in production, both strip the
  prefix and forward cookies untouched), and credential-less CORS is part
  of the CSRF posture (D9).
- **No secrets exist anywhere** (`engine/config.py` reads five `BVP_*`
  settings; the server's units carry `Environment=` lines, never `.env`).
  The Google client id is **public** (it is the `aud` of every ID token),
  so the GIS ID-token flow introduces no secret. No client secret is
  created.
- **No auth library is installed** — no `google-auth`, `phonenumbers`,
  `itsdangerous`, `pyjwt`. `requirements.lock` is a `-c` constraints file
  regenerated deliberately (its header says how).
- **Frontend**: SvelteKit 2 / Svelte 5 runes, `adapter-static` with the
  `index.html` fallback, `ssr = false` — no server routes, so every auth
  step lives in FastAPI. Zero runtime npm dependencies; tests are
  `node --test src/lib/*.test.js`, pure modules only. `$lib/owner.js` is the
  pattern for a storage-backed pure helper. `+layout.svelte` holds the
  `internal` route predicate and the two header CTAs, which is where the
  gate and the sign-in control belong. `parlay/+page.svelte` fetches in a
  mount `$effect`, so a future gate must wrap the children in the layout.
- **Service worker** caches only `/api/tips` and `/api/fixtures` (an
  allow-list) and bypasses non-GET; the shell is cached under `/` with no
  user state in it. No change needed.
- **Deploy**: `scripts/deploy.sh` migrates (step 4) before restarting the
  API (step 6); the API never migrates. nginx has no rate limiting and no
  CSP. `scripts/backup.sh` is a whole-database `pg_dump`, so the new
  tables are covered automatically — and the dump will now contain PII.

## 2. Decisions

Each with the recommendation the build below assumes. D2 is the owner's.

| # | decision | recommendation | why |
| --- | --- | --- | --- |
| **D1** | Provider and flow | Google only, **GIS ID-token flow** (`google.accounts.id` button → `POST /auth/google`); no OAuth code flow, no redirect URIs, no client secret | The SPA has no server; the ID token is verifiable server-side from public certs. A code flow needs a secret and a callback route the site has nowhere to host |
| **D2** | Session | **Owner, 2026-09-07:** DB-backed opaque token in an HttpOnly cookie, SHA-256 at rest | Revocable, sign-out-everywhere works, no signing secret to manage; matches raw-SQL/no-ORM |
| **D3** | Types in the new tables | `TIMESTAMPTZ` / `BOOLEAN`, stated as a departure in the migration's comment block | Sessions do time arithmetic (`expires_at > now()`, `now() + interval`). `POSTGRES_PLAN.md` D3 kept TEXT for *existing* columns so API output stayed byte-identical; that argument does not reach tables that did not exist then, and §1.2 there names these types for exactly this |
| **D4** | A `user_identities` (provider, subject) table | **Not now** | A second OAuth provider is one later migration (`INSERT … SELECT` of `google_sub`); a phone/OTP "native" login is a code table plus `phone_verified_at`, not a provider row. A join on every request for a provider that may never arrive |
| **D5** | Phone | Mandatory, once, E.164 via `phonenumbers`; **UNIQUE across accounts**; format only, no SMS | One number, one account is the property the number is being collected for. **Owner to confirm**: two people sharing a mobile cannot both have accounts; dropping the constraint is one word |
| **D6** | Country default | **Client-side, zero network**: IANA time zone → country, `navigator.language` region as fallback, `GB` last; the picker lets the user change it | No GeoIP database to license and update, no nginx module, identical through the Vite proxy and the service worker, and the answer is only a *default*. IP-based GeoIP (nginx `geoip2` + MaxMind) is the upgrade path if the owner wants a stronger signal |
| **D7** | Client id to the browser | `GET /auth/config` at runtime, not a Vite build variable | One `npm run build` is the same on every machine; the id already lives in the unit/`.env` for the server side |
| **D8** | Session length | **30 days sliding**, refresh written at most once a day per session, no absolute cap | A daily write throttle keeps a page that polls `/me` from turning every read into a write. `BVP_SESSION_DAYS` makes it a deployment setting |
| **D9** | CSRF | `SameSite=Lax` cookie **+** `Content-Type: application/json` required **+** `Sec-Fetch-Site: cross-site` refused **+** CORS stays credential-less. No token | Nothing here is a form. A cross-site JSON POST is a non-simple request, so it needs a preflight the middleware never grants; Lax keeps the cookie off cross-site POSTs anyway; `Sec-Fetch-Site` is the browser saying which it was |
| **D10** | Email | Stored lowercased, `email_verified` kept, **not unique**, unverified accepted; a token with **no email is refused** (`email NOT NULL`) | Identity is `google_sub`; email is display/contact. GIS tokens for the sign-in button always carry one; the guard is for the exception |
| **D11** | PII | Backups now carry names, emails, phones — recorded in `backup.sh`; deletion is manual SQL (`DELETE FROM users` cascades) until self-service is asked for | Say it where the next operator will read it. A published consent screen may require a privacy-policy URL on the domain |
| **D12** | What is gated now | **Nothing** | Owner scope. `require_user` ships because `/me/phone` needs it; the `/parlay` gate is §10 |
| **D13** | Rate limiting | nginx `limit_req` 10 r/min per IP, burst 10, on `/api/auth/` and `/api/me/phone` | An unauthenticated POST that makes an outbound call per hit needs a lid; the numbers are a guess for one NAT'd household, tune from the access log |
| **D14** | `citext` for email | No | Email is not a lookup key. If a feature ever looks users up by email, add an index on `lower(email)` then |
| **D15** | Cookie | `bvp_session`; `HttpOnly; SameSite=Lax; Path=/; Max-Age=30 days`; `Secure` from `BVP_COOKIE_SECURE` (default on; a development machine sets `0`) | `http://localhost` cannot receive a Secure cookie; production must not send one without it |
| **D16** | Token verification library | **`google-auth`** (+ `requests` transport) | Official handling of Google's `iss` values and cert endpoint; `PyJWT[crypto]` would pull `cryptography` and need hand-written `iss`/`aud`/JWKS logic |

## 3. Schema — `db/migrations/002_users.sql`

Applied by `db.migrate()` like any other file (stem `002_users` recorded in
`schema_migrations`); no runner change. The baseline's house style — a *why*
comment block per table — applies.

```sql
-- 002: accounts and sessions for Google sign-in (docs/AUTH_PLAN.md, B25).
-- Forward-only. Never edit an applied migration; add a new numbered one.
--
-- First tables written by the API rather than the cycle, and first to use
-- TIMESTAMPTZ/BOOLEAN: POSTGRES_PLAN.md D3 kept the baseline's UTC-text
-- columns so the API's output stayed byte-identical across the move; that
-- argument does not reach tables that did not exist then, and 1.2 names
-- real types for exactly these. Sessions do time arithmetic (expiry,
-- sliding refresh), which is why it matters here.
--
-- One row per Google account. `google_sub` is the identity (Google's stable
-- subject id), not the email, which Google allows to change. Token fields
-- are refreshed on every sign-in (ON CONFLICT DO UPDATE in api/main.py).
-- The phone is captured ONCE after the first sign-in (AUTH_PLAN.md D5):
-- E.164, normalised server-side with `phonenumbers`; the CHECK is the last
-- line of defence, not the validator. `phone_country` is the ISO 3166-1
-- alpha-2 region it was parsed under, for a later SMS step.
-- `phone_verified_at` stays NULL until SMS verification exists.
CREATE TABLE users (
    user_id           INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    google_sub        TEXT NOT NULL UNIQUE,
    email             TEXT NOT NULL,
    email_verified    BOOLEAN NOT NULL DEFAULT FALSE,
    name              TEXT,
    picture_url       TEXT,
    phone_e164        TEXT UNIQUE CHECK (phone_e164 ~ '^\+[1-9][0-9]{6,14}$'),
    phone_country     TEXT CHECK (phone_country ~ '^[A-Z]{2}$'),
    phone_captured_at TIMESTAMPTZ,
    phone_verified_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((phone_e164 IS NULL) = (phone_captured_at IS NULL)),
    CHECK (phone_e164 IS NULL OR phone_country IS NOT NULL)
);

-- One row per browser sign-in. The cookie holds a random 256-bit token; this
-- table holds its SHA-256, so a copy of the database or a backup (which now
-- carries PII -- scripts/backup.sh) cannot be replayed as a login. A session
-- ends when `expires_at` passes (sliding, refreshed at most daily by
-- api.main.current_user), when `revoked_at` is set (sign out), or when its
-- user is deleted (CASCADE). Revoked rows are kept, not deleted. The client
-- IP is NOT stored -- PII with no consumer; `user_agent` is, truncated.
CREATE TABLE user_sessions (
    session_id    INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    revoked_at    TIMESTAMPTZ,
    user_agent    TEXT
);

CREATE INDEX idx_user_sessions_user ON user_sessions (user_id);
CREATE INDEX idx_user_sessions_live ON user_sessions (expires_at) WHERE revoked_at IS NULL;
```

Deliberately **not** added now — each is one `ALTER TABLE` when its feature
is planned, and each is that feature's decision: `handle`/`display_name`
and `deleted_at` (community board), `role`, `user_identities` (D4).
`user_id` as a stable integer key is all a later board needs from here.

Test amendment: `tests/test_migrate_sqlite_to_pg.py` asserts
`COUNT(*) FROM schema_migrations == 1` ("the SQLite rows are not copied");
change it to compare against the on-disk migration set, as
`tests/test_seasons_and_db.py` already does. The copier's own table lists
are unaffected — it never sees these tables.

## 4. API

### 4.1 `api/auth.py` (new) — the seams tests monkeypatch; no SQL

```python
"""Sign-in primitives for api.main: Google token verification, session
tokens, phone normalisation. No SQL here; the endpoints own their queries."""
import hashlib, secrets
import phonenumbers
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from engine import config

COOKIE = "bvp_session"

def verify_google_token(credential: str) -> dict:
    """Claims of a Google ID token, or ValueError. google-auth checks the
    signature, `aud` (BVP_GOOGLE_CLIENT_ID), `iss` and `exp`. One HTTPS
    fetch of Google's certs per call -- once per sign-in, never per request."""
    if not config.GOOGLE_CLIENT_ID:
        raise ValueError("BVP_GOOGLE_CLIENT_ID is not set")
    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), config.GOOGLE_CLIENT_ID,
        clock_skew_in_seconds=10)

def new_token() -> str:             # 256 bits, URL-safe: the cookie value
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:  # what user_sessions.token_hash holds
    return hashlib.sha256(token.encode()).hexdigest()

def normalise_phone(raw: str, country: str) -> tuple[str, str]:
    """(E.164, region) or ValueError. `country` is the picked region; a
    number typed with its own '+' prefix overrides it."""
    try:
        number = phonenumbers.parse(raw, country)
    except phonenumbers.NumberParseException as error:
        raise ValueError("not a phone number") from error
    if not phonenumbers.is_valid_number(number):
        raise ValueError("not a valid phone number for that country")
    return (phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
            phonenumbers.region_code_for_number(number))

def regions() -> list[dict]:
    """[{code, dial}] for every region phonenumbers knows -- the picker's data."""
    return sorted(({"code": r, "dial": phonenumbers.country_code_for_region(r)}
                   for r in phonenumbers.SUPPORTED_REGIONS), key=lambda d: d["code"])
```

### 4.2 `api/main.py`

Imports: `from fastapi import Body, Request, Response`; `import psycopg`;
`from engine import config`; `from api import auth`.

**Docstring.** Line 1 `"""Read-only serving API.` becomes `"""The serving
API.` plus one paragraph: since `002_users.sql` the API also writes — only
to `users` and `user_sessions`, only from `POST /auth/google`,
`POST /auth/logout` and `POST /me/phone`; nothing a request can do changes
what was served; `tests/test_api.py` pins the write routes to that list.
The same one-line amendment goes on `get_conn`'s docstring ("mostly reads;
the write endpoints wrap multi-statement work in `conn.transaction()`") and
on `engine/db.py`'s `autocommit` note. The CORS block gains a comment that
credential-less CORS is part of D9.

**Dependencies:**

```python
def _same_site_json(request: Request) -> None:
    """Write endpoints take JSON from this site only (AUTH_PLAN.md D9)."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "send application/json")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "cross-site request refused")

def current_user(request: Request, conn: db.Connection = Depends(get_conn)) -> dict | None:
    token = request.cookies.get(auth.COOKIE)
    if not token:
        return None
    row = conn.execute(
        "SELECT u.user_id, u.email, u.name, u.picture_url, u.phone_e164,"
        "       u.phone_country, s.session_id"
        " FROM user_sessions s JOIN users u ON u.user_id = s.user_id"
        " WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > now()",
        (auth.hash_token(token),)).fetchone()
    if row is None:
        return None
    # Sliding expiry, written at most once a day per session (D8).
    conn.execute(
        "UPDATE user_sessions SET last_seen_at = now(),"
        " expires_at = now() + %s * interval '1 day'"
        " WHERE session_id = %s AND last_seen_at < now() - interval '1 day'",
        (config.SESSION_DAYS, row["session_id"]))
    return dict(row)

def require_user(user: dict | None = Depends(current_user)) -> dict:
    if user is None:
        raise HTTPException(401, "sign in required")
    return user
```

`require_complete_user` (403 `"phone_required"` when the phone is NULL) is
three lines and belongs to the gate phase (§10), not this one: nothing would
call it, and `/me/phone` must be reachable *without* a phone.

**Endpoints** — dict returns, `HTTPException` errors, `Body(...)` dicts (no
Pydantic for two two-field bodies):

```python
def _user_summary(row) -> dict:
    return {"user_id": row["user_id"], "name": row["name"], "email": row["email"],
            "picture_url": row["picture_url"], "phone_e164": row["phone_e164"],
            "phone_required": row["phone_e164"] is None}

@app.get("/auth/config")
def auth_config() -> dict:
    """Public client id (it is the `aud` of every token) + the region list."""
    return {"google_client_id": config.GOOGLE_CLIENT_ID, "regions": auth.regions()}

@app.post("/auth/google", dependencies=[Depends(_same_site_json)])
def auth_google(request: Request, response: Response,
                payload: dict = Body(...),
                conn: db.Connection = Depends(get_conn)) -> dict:
    credential = payload.get("credential")
    if not isinstance(credential, str) or not credential:
        raise HTTPException(400, "credential required")
    try:
        claims = auth.verify_google_token(credential)
    except ValueError as error:
        raise HTTPException(401, "invalid google credential") from error
    if not claims.get("email"):
        raise HTTPException(401, "google returned no email")
    token = auth.new_token()
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO users (google_sub, email, email_verified, name, picture_url)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (google_sub) DO UPDATE SET email = EXCLUDED.email,"
            "   email_verified = EXCLUDED.email_verified, name = EXCLUDED.name,"
            "   picture_url = EXCLUDED.picture_url, last_login_at = now()"
            " RETURNING user_id, email, name, picture_url, phone_e164",
            (claims["sub"], claims["email"].lower(), bool(claims.get("email_verified")),
             claims.get("name"), claims.get("picture"))).fetchone()
        conn.execute(
            "INSERT INTO user_sessions (user_id, token_hash, expires_at, user_agent)"
            " VALUES (%s, %s, now() + %s * interval '1 day', %s)",
            (row["user_id"], auth.hash_token(token), config.SESSION_DAYS,
             (request.headers.get("user-agent") or "")[:200]))
    response.set_cookie(auth.COOKIE, token, max_age=config.SESSION_DAYS * 86400,
                        path="/", httponly=True, secure=config.COOKIE_SECURE,
                        samesite="lax")
    return {"user": _user_summary(row)}

@app.get("/me")
def me(user: dict | None = Depends(current_user)) -> dict:
    """200 with `user: null` when anonymous, not 401 -- the layout asks on
    every load and a 401 is console noise."""
    return {"user": _user_summary(user) if user else None}

@app.post("/me/phone", dependencies=[Depends(_same_site_json)])
def set_phone(payload: dict = Body(...), user: dict = Depends(require_user),
              conn: db.Connection = Depends(get_conn)) -> dict:
    """One-time. The WHERE clause is the guard: a second call updates zero rows."""
    try:
        e164, region = auth.normalise_phone(str(payload.get("phone", "")),
                                            str(payload.get("country", "")).upper())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    try:
        cur = conn.execute(
            "UPDATE users SET phone_e164 = %s, phone_country = %s,"
            " phone_captured_at = now() WHERE user_id = %s AND phone_e164 IS NULL",
            (e164, region, user["user_id"]))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "that phone number is already on another account")
    if cur.rowcount == 0:
        raise HTTPException(409, "phone number already captured")
    return {"user": _user_summary({**user, "phone_e164": e164})}

@app.post("/auth/logout", status_code=204, dependencies=[Depends(_same_site_json)])
def logout(response: Response, user: dict | None = Depends(current_user),
           conn: db.Connection = Depends(get_conn)) -> None:
    if user:
        conn.execute("UPDATE user_sessions SET revoked_at = now() WHERE session_id = %s",
                     (user["session_id"],))
    response.delete_cookie(auth.COOKIE, path="/")
```

`with conn.transaction():` on an autocommit psycopg 3 connection issues
BEGIN/COMMIT around the two sign-in statements; the single-statement UPDATEs
need nothing. Read `config.X` at call time, not into module constants, so a
test can `monkeypatch.setattr(config, …)` the way `conftest._calendar_off`
does.

**Wire shapes.**

| call | body | 200 | errors |
| --- | --- | --- | --- |
| `GET /auth/config` | — | `{google_client_id, regions: [{code, dial}]}` | — |
| `POST /auth/google` | `{credential}` | `{user}` + `Set-Cookie` | 400 no credential · 401 invalid / no email · 415 not JSON · 403 cross-site |
| `GET /me` | — | `{user}` or `{user: null}` | — |
| `POST /me/phone` | `{phone, country}` | `{user}` | 400 invalid · 401 no session · 409 already captured / on another account |
| `POST /auth/logout` | `{}` | 204, cookie cleared | — |

`user` = `{user_id, name, email, picture_url, phone_e164, phone_required}`.

**Route-table pin.** `test_the_api_exposes_no_write_routes` becomes
`test_the_only_write_routes_are_the_account_ones`: the set of `(path,
method)` non-GET routes **equals** `{("/auth/google","POST"),
("/auth/logout","POST"), ("/me/phone","POST")}`, so any later POST goes red
until listed on purpose. The test module's docstring is amended alongside.

Other "read-only" prose to amend honestly: `deploy/systemd/bvp-api.service`
(lines 1, 12, 32), `docs/STATE.md` API row, `web/src/lib/api.js` line 1,
`engine/db.py` line 65, `docs/DEPLOY.md`'s description of the API.

## 5. Config

`engine/config.py`, after `DATABASE_URL`:

```python
#: Google OAuth client id for sign-in (docs/AUTH_PLAN.md). Public, not a
#: secret -- it is the `aud` of every ID token -- but environment, not code.
#: Empty means sign-in is unconfigured: /auth/google answers 401.
GOOGLE_CLIENT_ID = setting("BVP_GOOGLE_CLIENT_ID")
#: Session lifetime in days, sliding (api.main.current_user).
SESSION_DAYS = int(setting("BVP_SESSION_DAYS", "30"))
#: Secure cookie: on unless a development machine says otherwise --
#: http://localhost cannot receive one at all.
COOKIE_SECURE = setting("BVP_COOKIE_SECURE", "1") == "1"
```

- `.env.example`: a `# --- sign-in ---` section with
  `# BVP_GOOGLE_CLIENT_ID=….apps.googleusercontent.com`, `BVP_COOKIE_SECURE=0`
  (uncommented, with the localhost sentence), `# BVP_SESSION_DAYS=30`.
- `deploy/systemd/bvp-api.service`: one line
  `Environment=BVP_GOOGLE_CLIENT_ID=<id>` under the store block, commented
  as public and tied to the console's authorised origins. The other two keep
  their defaults, which are the production values. `RestrictAddressFamilies`
  already permits the outbound HTTPS call to Google's cert endpoint;
  `ProtectSystem=strict` is fine (certifi's bundle is read from
  site-packages).
- `pyproject.toml` `serve` extra: `google-auth>=2.30`, `requests>=2.31`,
  `phonenumbers>=8.13` — API-only, `engine/` never imports them. Then
  regenerate `requirements.lock` on the Ubuntu target per its header and
  re-run `pytest -q` there.

## 6. Frontend

- **`web/src/app.html`**: `<script src="https://accounts.google.com/gsi/client"
  async defer></script>` after the gtag block, with a comment like the
  fonts one — third-party; if blocked there is no button, never a broken
  page.
- **`web/src/lib/api.js`**: `class ApiError extends Error` carrying `status`
  (message text unchanged, so nothing in the pages or tests moves); a
  `post(path, body)` helper — `fetch(url, { method: 'POST', credentials:
  'same-origin', headers: { 'content-type': 'application/json' }, body:
  JSON.stringify(body) })`, throws `ApiError` on non-ok, returns `null` on
  204 else JSON. The "read-only" header comment is fixed.
- **`web/src/lib/session.js`** (new): wrappers `getAuthConfig`, `getMe`
  (→ `.user`), `signInWithGoogle(credential)`, `savePhone(phone, country)`,
  `signOut()`; pure, tested helpers `phoneRequired(user)`, `firstName(user)`,
  `plausiblePhone(raw)` — a *light* client check that only enables the
  button; the server's `phonenumbers` verdict is what is shown.
- **`web/src/lib/country.js`** (new, D6): `ZONE_COUNTRY` (IANA zone → ISO-2,
  generated once from tzdata's `zone1970.tab`, first country per zone,
  source and date in the header comment), `DEFAULT_COUNTRY = 'GB'`,
  `countryFromLocale(lang)`, and `detectCountry(zone, lang, known)` = zone
  map → locale region → default, constrained to the `known` codes. The
  layout calls it with `Intl.DateTimeFormat().resolvedOptions().timeZone`,
  `navigator.language` and the region codes from `/auth/config`. Country
  *names* come from `Intl.DisplayNames(['en'], { type: 'region' })` at
  render time and dial codes from the API, so the browser carries no other
  country data.
- **`web/src/routes/+layout.svelte`**:
  - State, component-local runes, no store: `me`, `authReady`, `cfg`,
    `phone`, `country`, `phoneError`, `saving`, `buttonHost` (`bind:this`).
  - On mount: `cfg = await getAuthConfig(); me = await getMe(); authReady =
    true;` then, when `!me`, poll `window.google?.accounts?.id` (the script
    is async; ≤ 5 s) → `initialize({ client_id, callback, ux_mode: 'popup'
    })` + `renderButton(buttonHost, { theme: 'filled_black', size: 'medium',
    shape: 'pill', text: 'signin_with' })`. The host is `{#if !me}`-
    conditional, so sign-out re-mounts and re-renders it. The callback sets
    `me = await signInWithGoogle(credential)`; failure shows a small inline
    error.
  - Header `.actions`: keep both CTAs; append, once `authReady`, either the
    avatar (`referrerpolicy="no-referrer"`) + `firstName(me)` + a "Sign out"
    link-button, or the `.gsi` host. The flex row already wraps at ≤ 820 px.
  - **Phone gate**, directly after `</header>`: `{#if phoneRequired(me)}` a
    `.veil` (fixed, inset 0, `rgba(14,14,17,.85)`, z-index above the sticky
    header) holding a `<form class="state box phone">` in the `.state.box`
    idiom from `parlay/+page.svelte`: heading, one sentence of copy, a
    `<select>` of regions (name + `+dial`), `<input type="tel"
    inputmode="tel" autocomplete="tel">`, a server-error line in `--bad`, a
    "Save number" `.cta` disabled until `plausiblePhone`, and "Sign out
    instead". `country` is initialised from `detectCountry` once `cfg`
    arrives. 400 → show the server's message; 409 "another account" →
    show; 409 "already captured" → refresh `me`. A modal in the layout
    rather than an `/account` route: reachable from every route, no
    navigation, no service-worker consideration, no route file.
- **`web/src/service-worker.js`**: no change — `/api/me` and `/api/auth/*`
  are not in `OFFLINE_API`, non-GET bypasses the worker, the shell under `/`
  carries no user state. One sentence in its header comment says so.
- **No runtime npm dependency**; `package.json` stays devDeps-only.

## 7. Tests

**Python — `tests/test_auth.py` (new).** Fixture `auth_client(make_database,
monkeypatch)`: migrate a clone; `monkeypatch.setattr(auth,
"verify_google_token", …)` returning claims from a `CLAIMS` dict keyed by a
fake credential (unknown → `ValueError`); `monkeypatch.setattr(config,
"COOKIE_SECURE", False)` (httpx's jar drops Secure cookies on
`http://testserver`) and `"GOOGLE_CLIENT_ID", "test-client"`;
`app.dependency_overrides[get_conn] = _override(url)` (reuse
`tests/test_api.py`'s `_override`); `TestClient(app)`. A `post_json` helper
sets the JSON content type. Cases:

1. sign-in creates one user (email lowercased) and one session whose
   `token_hash == sha256(cookie)`; cookie carries `HttpOnly`, `SameSite=lax`,
   `Path=/`, `Max-Age=2592000`; `phone_required` is true
2. `Secure` is present in the raw `Set-Cookie` when `COOKIE_SECURE` is True
3. a second sign-in is the same user with a refreshed `name`, a moved
   `last_login_at`, and a second session row
4. bad credential → 401 and no rows; missing credential → 400; non-JSON →
   415; `Sec-Fetch-Site: cross-site` → 403; a token without an email → 401
5. `/me` is anonymous without a cookie and with a forged one;
   `phone_required` flips after the phone is saved
6. phone normalisation: `("07700 900123", "GB")` → `+447700900123` / `GB`;
   `("+254712345678", "GB")` → `KE` (a typed prefix wins); invalid → 400;
   second POST → 409 with the row unchanged; a phone already on another
   account → 409; no session → 401
7. an expired session is anonymous; a revoked one is anonymous
8. sliding refresh: plant `last_seen_at = now() - 2 days`, `expires_at =
   now() + 1 day`; the first `/me` moves `expires_at` to ≈ now + 30 d; the
   second leaves it byte-equal
9. logout → 204, `revoked_at` set, `Set-Cookie` with `Max-Age=0`, the next
   `/me` anonymous; logout without a cookie is also 204
10. `/auth/config` serves the client id and the regions (`GB` dial 44)
11. direct unit tests of `auth.normalise_phone` and `auth.hash_token`

Plus the amended pins in `tests/test_api.py` (the route table) and
`tests/test_migrate_sqlite_to_pg.py` (the migration count).

**JS — `web/src/lib/country.test.js`, `web/src/lib/session.test.js`**
(`node:test`, the `owner.test.js` header): a dozen representative zones
(GB, KE, NG, GH, UG, ZA, US, IN, IE, DE, AU, BR); `countryFromLocale('en-GB')`
and `('en')`; an unknown zone with a bare locale → the default; a detected
code absent from `known` → the default; `phoneRequired`, `firstName` (name
and email fallback), the `plausiblePhone` accept/reject set.

## 8. Ops and deploy

1. **Google Cloud console** (owner, one-off): OAuth consent screen
   (External; app name, support email, authorised domain = the site's
   domain; **publish** it, or sign-ins are capped to listed test users) →
   Credentials → OAuth client ID → Web application. Authorised JavaScript
   origins: `https://<domain>`, `http://localhost:5173`, `http://localhost`
   (GIS wants the bare one too for local development). No redirect URIs.
   Copy the client id into `.env` and the unit. No client secret is created.
2. **Verify HTTPS** (not build it): `curl -sI https://<domain>/api/health`
   → 200, `http://` → 301; confirm `bvp.conf.template` (not the `-http`
   one) is what is rendered on the VM. Update `DEPLOY.md` step 5b's row.
3. **Migration order** needs no change: `deploy.sh` migrates at step 4,
   before the restart at step 6; the old API never touches the new tables.
4. **Unit file**: the one `Environment=` line; copy, `daemon-reload`,
   restart (the file's own ritual); wording fixes at lines 1, 12, 32.
5. **nginx** (D13): a new tracked `deploy/nginx/bvp-limits.conf` (no
   variables, so not a template) with `limit_req_zone $binary_remote_addr
   zone=bvp_auth:1m rate=10r/m;` copied to `/etc/nginx/conf.d/`; in
   `bvp.conf.template`, `location /api/auth/ { limit_req zone=bvp_auth
   burst=10 nodelay; proxy_pass http://127.0.0.1:8000/auth/; <the same
   proxy_set_header lines>; }` and `location = /api/me/phone { … proxy_pass
   http://127.0.0.1:8000/me/phone; }` — the longest prefix wins over
   `/api/`. `nginx -t`, reload. Documented in `DEPLOY.md` §5.3.
6. **`scripts/backup.sh`**: the "WHAT THIS PROTECTS" paragraph gains
   `users` and `user_sessions` and a sentence that the dump now contains
   personal data (names, emails, phones); the row-count block gains both.
7. **Runbook entry, "sign-in is down"**: button missing → the GSI script is
   blocked or `/auth/config` returns an empty client id; 401 on sign-in →
   wrong client id, or the origin is not authorised in the console; every
   sign-in 401 while `/me` works → Google's cert endpoint unreachable from
   the VM (fails closed; the read side is unaffected).

## 9. Build phases and verification

| phase | work | verify |
| --- | --- | --- |
| **A** backend (~1.5 d) — **built 2026-09-07**: 702 pass (28 new), `002_users` applied to the dev store, 401 unconfigured; logout returns an explicit empty `Response` (FastAPI refuses `status_code=204` on a bodied signature); `phone_country` is the region derived from the number, not the one picked | `002_users.sql`; `engine/config.py`; `api/auth.py`; `api/main.py` dependencies, five endpoints, docstrings; `pyproject.toml`; `tests/test_auth.py`; the two amended pins | `pytest -q` green (last quoted 673 — re-run, don't quote; expect ≈ +25); on the dev store `python -c "from engine import db; print(db.migrate(db.connect()))"` prints `['002_users']`; `curl -X POST localhost:8000/auth/google -H 'content-type: application/json' -d '{"credential":"x"}'` → 401. Independently mergeable: no behaviour change for anonymous readers |
| **B** frontend (~1.5 d) — **built 2026-09-07**: 33 web tests (8 new), build clean, 22-check Playwright click-through on a seeded `bvp_scratch` (planted sessions; anonymous / forged / expired cookies, the gate, zone-detected country, client and server validation, the one-time write, the cross-account 409, sign-out from the gate and from the header at 390 px). `ZONE_COUNTRY` is generated from `zone.tab` *first* (Africa/Accra is GH; tzdata has folded it into Abidjan), then `zone1970.tab`, then the links | `app.html`; `api.js` `post`/`ApiError`; `session.js`; `country.js` + zone table; `+layout.svelte` button, header state, phone modal; the JS tests | `cd web && npm test` (≈ +10 from 25); `npm run build` clean; the dev stack (`scripts/dev.ps1`, a real client id, `BVP_COOKIE_SECURE=0`): real Google sign-in → modal with the detected country → an invalid number shows the server's message → a valid one saves and the modal closes → a refresh keeps the session → sign out clears it. Playwright click-through against a seeded `bvp_scratch` (the project recipe): Google's popup cannot be scripted, so seed `users` + `user_sessions` rows and set the cookie on the context; check the header name, the modal for a phone-less user, the 409 path, sign-out, the 390 px layout; drop `bvp_scratch` after |
| **C** deploy + docs (~0.5–1 d) — **done 2026-09-07, LIVE** (`ad9995f`): `bvp-limits.conf`, the two `limit_req` locations in `bvp.conf.template`, the unit's client-id line and wording, `backup.sh`, pins appended to `requirements.lock`, `DEPLOY.md` §2.7/§5.3/§7, `RUNBOOK.md` §5.10; the owner ran §9.1 on the VM — real sign-in verified on `https://babavanga.net`, backup run. Still open: a full `requirements.lock` regeneration on the VM | lock regen; unit line; nginx limits + template; `backup.sh`; Google console; `deploy.sh`; this file's §11, `BACKLOG.md` B25, `OUTSTANDING.md`, `STATE.md`, `DEPLOY.md`, `.env.example`, `docs/notes` | `deploy.sh` shows `applied: ['002_users']`, the suite green on the VM, `nginx -t` ok; a real sign-in on the domain over HTTPS; DevTools shows the cookie Secure/HttpOnly/Lax; `journalctl -u bvp-api` clean; a backup run prints `users=… user_sessions=…` |

Total **≈ 3.5–4 days**. No rule, cycle, grading or ledger change.

### 9.1 The VM, in order — owner's checklist

Between matchdays, as `POSTGRES_PLAN.md` Phase C was run: one step, confirm,
the next. The schema change is additive (two empty tables), so there is no
rollback beyond `git checkout` of the previous commit and a restart.

1. **Commit and push** the working tree (everything B25 is uncommitted until
   then); `git status` clean on the VM's branch before `deploy.sh` will run.
2. **Google Cloud console** (once): the OAuth client's authorised JavaScript
   origins include `https://<domain>`; the consent screen is published.
3. **nginx, before the deploy** — after a `git pull --ff-only` on the VM,
   since steps 3 and 4 read files from the checkout (`deploy.sh --no-pull`
   in step 5 then skips the pull it would otherwise repeat):
   `sudo cp deploy/nginx/bvp-limits.conf
   /etc/nginx/conf.d/`, re-render `bvp.conf.template` (`DEPLOY.md` §5.3),
   `sudo nginx -t`, reload. The new locations proxy to paths that 404 until
   the API restarts — harmless.
4. **The unit**: the tracked file keeps its empty
   `Environment=BVP_GOOGLE_CLIENT_ID=` line (`DEPLOY.md` §3.6); the id goes in
   a drop-in, which a later `cp` of the unit cannot wipe and which overrides
   the empty line because drop-ins apply after the unit:
   `/etc/systemd/system/bvp-api.service.d/google.conf` containing
   `[Service]` and `Environment=BVP_GOOGLE_CLIENT_ID=<id>`. Then copy the
   unit, `sudo systemctl daemon-reload`, and `systemctl cat bvp-api | grep
   GOOGLE` shows both lines. Do not restart yet: the deploy migrates first.
5. **`scripts/deploy.sh`**: pull → pip (the appended pins install
   `google-auth`, `requests`, `phonenumbers`) → build → **migrate** (expect
   `applied: ['002_users']`) → `pytest -q` (expect the 28 auth tests among
   the green) → restart → `/health`.
6. **Verify over HTTPS**: the three curls in `DEPLOY.md` §5.3's sign-in
   block; then a real sign-in in a browser — the button renders, the popup
   completes, the phone form appears with the right country, a number
   saves, DevTools shows `bvp_session` as HttpOnly / Secure / Lax, a reload
   keeps the session, Sign out clears it. `psql bvp -c "SELECT user_id,
   email, phone_e164, phone_country FROM users"` shows the row.
7. **Backup**: `sudo systemctl start bvp-backup`; the log line now ends
   `users=1  user_sessions=…`.
8. **Docs**: tick `docs/notes` line 12, `STATE.md`'s B25 row to "live",
   `OUTSTANDING.md` entry, `requirements.lock` header date if the lock is
   regenerated on the VM.

## 10. Future hooks — documented, not built

- **`/parlay` behind sign-in** (`docs/notes`): beside `internal` in
  `+layout.svelte`, `const requiresAuth = $derived(['/parlay'].includes($page.url.pathname))`;
  render `{@render children()}` only when `!requiresAuth || (authReady && me
  && !phoneRequired(me))`, otherwise a sign-in prompt panel. Because the
  layout wraps the children, the parlay page's mount `$effect` never fires
  while gated — the page itself is untouched. Server side: add
  `require_complete_user` (401 anonymous, 403 `phone_required`) and
  `Depends` it on `GET /parlay`. About half a day.
- **Shared session state**: when a *page* itself needs `me` (the community
  board), lift `me`/`authReady` from the layout into
  `web/src/lib/session.svelte.js` as a `$state` object — the first point at
  which shared reactive state earns a file. Not before.
- **Community board** (parlays, likes, comments): `user_id` is the foreign
  key; `handle` and `deleted_at` are that plan's migration.
- **SMS verification / WhatsApp**: `phone_e164`, `phone_country` and
  `phone_verified_at` are already in place; a code table and a sender are
  that plan's.
- **A second provider or a phone login**: D4.

## 11. Risks and open items for the owner

1. **D6 country detection** is a default — right for most, wrong for
   travellers and VPN users; the picker fixes it. IP GeoIP is the upgrade
   path if wanted.
2. **D5 phone UNIQUE** — confirm, or drop the one word and accept shared
   numbers.
3. **D12 gating nothing** — the header will show sign-in on a site that
   gives signed-in users nothing extra yet. Building the parlay gate in the
   same pass is ≈ +0.5 d; the notes suggest it is next anyway.
4. **PII**: backups and the Azure container now hold names, emails and
   phones; there is no self-service deletion; the privacy copy in the footer
   and the modal is the owner's to approve. A published consent screen may
   require a privacy-policy URL on the domain.
5. **Google's button** is Google's iframe, not the site's tokens; a
   custom-styled button needs One Tap/FedCM, which is less reliable —
   accept the Google look. In an installed PWA (`display: standalone`) the
   popup flow should be checked on iOS.
6. **Availability**: each sign-in makes one outbound HTTPS call to Google's
   cert endpoint; if it is unreachable, sign-in fails closed with 401 and
   the read side is unaffected.
7. **Rate-limit numbers** are a guess (10 r/min, burst 10, per IP) sized for
   one NAT'd household; tune from the access log.
8. **Side-findings, out of scope**, for a separate issue: `api/main.py`
   comments still cite SQLite-era migrations 002–006 that no longer exist on
   disk; `STATE.md`'s header date and `DEPLOY.md` step 5b ("blocked: no
   domain") are stale; an untracked `web/vite.config.js.timestamp-*.mjs`
   build artifact is sitting in the tree.
