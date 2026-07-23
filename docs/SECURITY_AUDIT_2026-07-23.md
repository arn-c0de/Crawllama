# Security Audit — CrawlLama

**Date:** 2026-07-23
**Branch:** 1.4.11
**Method:** Multi-agent static review across 5 domains (API/web layer, AI-agent core, OSINT sources & crawling, crypto/secrets/config, dependencies/CI/infra). Top findings manually verified against source.

## Executive Summary

CrawlLama is a **notably well-hardened** codebase. The classic high-impact sinks are absent: no `eval`/`exec`/`subprocess`/`os.system`/`pickle` on untrusted input, no `verify=False`, no committed secrets, no `pull_request_target` misuse. SSRF defense is genuinely strong (DNS-rebinding double-check + IP-pinned adapter + per-hop redirect re-validation). Crypto uses `secrets`/`hmac.compare_digest`/Fernet correctly.

**No CRITICAL or HIGH exploitable issues were found.** The findings below are MEDIUM and lower — hardening gaps, misconfiguration hazards, and one concrete code defect.

| # | Severity | Area | Issue | Status |
|---|----------|------|-------|--------|
| 1 | MEDIUM | API | DEV_MODE loopback guard bypassable via uvicorn CLI `--host` | ✅ **Fixed** |
| 2 | MEDIUM | Secrets | `data/api_keys.json` written world-readable (no `0o600`) | ✅ **Fixed** |
| 3 | MEDIUM | Secrets | Audit log loses `0o600` after rotation | ✅ **Fixed** |
| 4 | MEDIUM | Agent | Indirect prompt injection: crawled content → final-answer LLM (English-only blacklist) | ⚠️ Open (bounded) |
| 5 | MEDIUM/LOW | Agent | Crawled body text not HTML-escaped (XSS if response rendered as HTML) | ⚠️ Open (frontend-dep.) |
| 6 | LOW–MEDIUM | OSINT | Query/URL injection in `github_source.py` (raw email in URL) | ✅ **Fixed** |
| 7 | LOW | API | CORS `allow_credentials=True` with no guard against `ALLOWED_ORIGINS="*"` | ✅ **Fixed** |
| 8 | LOW | API | Auth failures not rate-limited (invalid-key brute-force / resource use) | ✅ **Fixed** |
| 9 | LOW | Secrets | `APIKeyManager` ephemeral-secret fallback with no fail-closed guard | ✅ **Fixed** (persisted secret) |
| 10 | LOW | Secrets | `secret_scanner.py` writes plaintext matched secrets to disk | ⚠️ Open |
| 11 | LOW | OSINT | aiohttp scraping paths lack redirect re-validation & size limits | ⚠️ Open |
| 12 | LOW | OSINT | Direct `requests` breach sources bypass central size guard | ⚠️ Open |
| 13 | LOW | Infra | `curl \| sh` bootstrap of `uv` in `setup.sh` | ⚠️ Open |
| 14 | LOW | CI | Bandit/Jekyll workflows pinned to stale branches — SAST not running | ✅ **Fixed** (bandit → `main`) |
| 15 | INFO | Deps | chromadb 1.5.9 unpatched CVE (mitigated: in-process client only) | ℹ️ Accepted (mitigated) |

## Remediation Applied (2026-07-23)

- **#1** `app.py` — new `_dev_bypass_allowed(request)` gates every DEV_MODE relaxation (auth, CSRF middleware, CSRF token, RBAC) on the client being loopback. Verified: loopback → bypass, remote/`0.0.0.0`/unknown → full auth (401). Closes the `uvicorn --host 0.0.0.0` gap the startup guard cannot see.
- **#2** `core/api_key_manager.py` — key-store dir `chmod 0o700`; `_store_key_file` writes via `os.open(..., 0o600)` + post-write `chmod 0o600`.
- **#3** `core/audit_logger.py` — `_SecureRotatingFileHandler` re-applies `0o600` on every `_open()`/rollover. Verified across forced rotations.
- **#6** `core/osint/sources/github_source.py` — query passed via `params={"q": ...}` (URL-encoded) instead of raw interpolation.
- **#7** `app.py` — `ALLOWED_ORIGINS` split entries stripped; a literal `"*"` is rejected (falls back to localhost defaults) so a credentialed wildcard can't be configured.
- **#9** `core/api_key_manager.py` — `_load_or_create_secret()` persists an owner-only secret when `RATE_LIMIT_SECRET` is unset, so stored key hashes survive restarts instead of using a per-process ephemeral secret.
- **#8** `app.py` — per-IP failed-auth throttle (`AUTH_FAILURE_LIMIT`, default 20/min) checked *before* the storage-backed `validate_key()` lookup; records failures on missing/invalid keys, returns 429 when exhausted. Verified: `[401×5 → 429]` at limit 5, and a valid key from a different IP is unaffected (per-IP, not global).
- **#14** `.github/workflows/bandit.yml` — push/PR triggers moved from stale `v1.4.2` to `main` so SAST runs on current code.

**Verification:** `app.py` imports cleanly (45 routes); full `tests/security/` suite — **232 passed**.

Remaining open items (#4, #5, #10, #11, #12, #13) are bounded/lower-risk hardening; see details below.

---

## MEDIUM Findings

### 1. DEV_MODE loopback guard bypassable via uvicorn CLI `--host`
**File:** `app.py:495-520` (`_enforce_dev_mode_loopback_only`)

The fail-closed guard reads the bind host **only from env vars** (`CRAWLLAMA_HOST`/`HOST`/`UVICORN_HOST`, default `127.0.0.1`). Launching as `CRAWLLAMA_DEV_MODE=true uvicorn app:app --host 0.0.0.0` (a common container/systemd pattern) makes the guard see the default `127.0.0.1`, pass, and uvicorn still binds externally. The shipped `run_api.sh` uses `python app.py` and is safe.

**Impact:** DEV_MODE disables API-key auth, CSRF and RBAC on **every** endpoint including `/admin/*`, `/config`, `/dev/api-key` — a full unauthenticated admin surface exposed on the network.

**Fix:** Pass the actual uvicorn-resolved bind host into the guard (or bind inside `app.py` only), **and** enforce the loopback check per-request in the dev-mode auth/CSRF shortcut using `request.client.host` (as `/dev/api-key` already does at `app.py:2700`).

### 2. `data/api_keys.json` written world-readable
**File:** `core/api_key_manager.py:366-376` (`_store_key_file`), `:130-131` (parent `mkdir`)

Created via `open(..., 'w')` under default umask (~`0644`); parent dir `mkdir`'d with no mode. Unlike `audit_logger` and `secure_config`, no `0o600`/`0o700` restriction is applied. **Verified.**

**Impact:** Any local user can read all key records (`user_id`, `key_id`, expiry, HMAC key hashes). Hashes are keyed HMAC (not directly reversible) but metadata leaks; hashes become brute-forceable if `RATE_LIMIT_SECRET` is weak/ephemeral (see #9).

**Fix:** Create via `os.open(..., 0o600)` (mirror `secure_config._get_or_create_encryption_key`), `mkdir(..., mode=0o700)`, and `chmod(0o600)` after each write.

### 3. Audit log loses `0o600` after rotation
**File:** `core/audit_logger.py:171-181`

Only the initial `audit.json` is `chmod 0o600`. On rollover `RotatingFileHandler` reopens a fresh base file via its own `_open()` under default umask (~`0644`).

**Impact:** After the first rotation the active audit log — containing PII (IP addresses, user identifiers) — becomes world-readable.

**Fix:** Subclass the handler to `chmod 0o600` in `_open()`/`doRollover()`, or set a restrictive umask around the handler.

### 4. Indirect prompt injection into final-answer LLM via crawled content
**Files:** `tools/page_reader.py:60-115` (`filter_prompt_injection`) → `core/agent/agent.py:1566` → `tools_flow.generate_final_answer`

Untrusted page bodies are sanitized only by a ~16-entry **English-only regex blacklist**. Injected instructions phrased differently, in German/other languages, or as novel manipulations pass into the LLM prompt that produces the user-facing answer.

**Impact:** An attacker controlling a crawled page can steer the **summary/answer** the user sees (misinformation, social engineering, planting a chosen link). It **cannot** hijack tools or exfiltrate data — routing and tool selection never depend on crawled content (verified: hardcoded 3-tool allowlist, structural `[EXTERNAL_WEB_CONTENT_*]` trust markers re-wrapped once, obfuscation decoded before matching).

**Fix:** Treat the blacklist as defense-in-depth only. Rely primarily on the structural trust markers plus a strong system-prompt instruction to never obey instructions inside `[EXTERNAL_WEB_CONTENT_*]`.

### 5. Crawled body text not HTML-escaped
**File:** `tools/page_reader.py:406-409`

`clean_html` strips tags but entity-encoded markup in a page is decoded to literal `<img ...>` and passed only through injection filtering — **no `html.escape`**. `sanitize_for_output` (escaping) is applied only to extracted emails/phones/links, not the main body.

**Impact:** If any consumer (web UI/API) renders the agent response as HTML/rich markdown, stored XSS from a crawled page is possible. Inert in a pure-terminal CLI.

**Fix:** HTML-escape crawled body text at the output boundary, or confirm the rendering layer escapes.

---

## LOW Findings

### 6. Query/URL injection in GitHub breach source
**File:** `core/osint/sources/github_source.py:29-30` — **Verified.**

```python
query = f'"{email}" in:file'
url = f"https://api.github.com/search/code?q={query}"
response = requests.get(url, headers=headers, timeout=15)
```

Email is interpolated raw into the URL. Every sibling source was hardened (intelx uses `params=`, hibp/dehashed use `quote(..., safe='')`) — this one was missed. `EmailIntelligence.check_data_breaches()` → `BreachManager.query_all()` reaches the sink without `validate_syntax()`, so an email containing `&`/`#`/`?` can inject/append query params or truncate the query. Bounded impact (public search API, no secrets in URL).

**Fix:**
```python
requests.get("https://api.github.com/search/code",
             headers=headers, params={"q": f'"{email}" in:file'}, timeout=15)
```

### 7. CORS `allow_credentials=True` with no `"*"` guard
**File:** `app.py:145-168`

Default origins are safe (localhost) and a warning is logged, but `cors_origins` is taken verbatim from env and combined with `allow_credentials=True`. Setting `ALLOWED_ORIGINS="*"` produces the dangerous credentialed-wildcard/origin-reflection combination. Also `split(",")` doesn't `.strip()`, so padded origins silently fail to match.

**Fix:** Reject/ignore `"*"` when `allow_credentials=True`; `.strip()` each split origin.

### 8. Authentication failures not rate-limited
**File:** `app.py:928` (`check_rate_limit` depends on `verify_api_key`)

`verify_api_key` runs before rate limiting and the counter only records authenticated principals, so invalid-key requests are never throttled — each still invokes `validate_key()` (storage lookup). Auth brute-force / resource-exhaustion vector, mitigated by 256-bit key entropy.

**Fix:** Apply an IP-based rate limit before/independent of authentication.

### 9. `APIKeyManager` ephemeral-secret fallback, no fail-closed guard
**File:** `core/api_key_manager.py:134`

```python
self.secret = os.getenv("RATE_LIMIT_SECRET", secrets.token_bytes(32))
```

`app.py:524-535` refuses to start with an ephemeral secret outside dev mode, but `APIKeyManager` re-reads env independently and silently falls back to a per-process random secret when imported directly (scripts/tests/alt entrypoints). Not a confidentiality break, but stored key hashes stop validating across restarts / differ per worker → self-DoS.

**Fix:** Share one guarded secret source (fail closed if unset outside dev).

### 10. Secret scanner writes plaintext secrets to disk
**File:** `scripts/secret_scanner.py:129-144, 166-167`

Always writes `secret_scan_report.txt` (project root) with full matched secret strings + context, default permissions. Mitigated by `.gitignore` but still world-readable locally.

**Fix:** Restrict report to `0o600`, redact/truncate the `match` field, make output opt-in.

### 11. aiohttp scraping paths lack redirect re-validation & size limits
**Files:** `core/osint/social_intel.py:493,501`, `core/osint/ip_intel.py:214`

Fetch with `allow_redirects=True` directly on `aiohttp.ClientSession`, no per-hop SSRF re-validation and no size cap — unlike the hardened `utils/safe_fetch.py`. Low exploitability: fixed trusted hosts, regex-validated usernames, `ipaddress`-validated IPs. Residual risk: open-redirect on trusted host / hostile upstream returning unbounded body.

**Fix:** Route through `safe_fetch` or add a size guard.

### 12. Direct `requests` breach sources bypass central size guard
**Files:** `hibp_source.py`, `dehashed_source.py`, `snusbase_source.py`, `leakcheck_source.py`, `intelx_source.py`, `github_source.py`

Timeouts set but no response-size limit before `response.json()`. Fixed trusted hosts → theoretical DoS only.

### 13. `curl | sh` bootstrap of `uv`
**File:** `setup.sh:27-29`

`curl -LsSf https://astral.sh/uv/install.sh | sh` (+ `wget` fallback). HTTPS + `-f` present; a compromised endpoint/MITM would run arbitrary code as the user at install time. The same string in `run.sh`/`run_api.sh`/`health-dashboard.sh` is only inside `echo` text (not a risk).

**Fix (optional):** Download to file, verify pinned checksum/signature, then execute.

### 14. Security workflows pinned to stale branches
**Files:** `.github/workflows/bandit.yml:16-19` (branch `v1.4.2`), `jekyll-gh-pages.yml:7` (`v1.4.5`)

Current branch is `1.4.11`, so **Bandit SAST effectively does not run**. Operational coverage gap.

**Fix:** Update branch filters to the active release / default branch.

---

## INFO

### 15. chromadb 1.5.9 unpatched CVE
**File:** `pyproject.toml:32` / `uv.lock:671`

CVE-2026-45829 "ChromaToast" (pre-auth RCE) has no patched release. Used solely as an in-process `PersistentClient`, so **not exploitable here**. Correctly documented in the pin comment. Bump the moment upstream ships a fix.

### Other minor notes
- `utils/secure_hash.py:32` — `hmac_sha256_hex` defaults to `sha3_256` despite its name (cosmetic).
- `utils/secure_config.py` — `.encryption_key` stored beside its ciphertext `.env`; defense-in-depth limitation, not exploitable. Consider secrets-manager/OS-keystore in production.
- `.env.example` could not be read by the auditor (directory permissions); manually confirm it contains only placeholders.

---

## Protections Verified as Correctly Implemented

**SSRF (excellent):** `utils/validators.py` + `utils/safe_fetch.py` — scheme allowlist, DNS resolution blocking loopback/private/link-local (incl. `169.254.169.254` AWS metadata)/reserved/multicast/IPv6-ULA; subdomain-boundary-aware domain allowlist; **DNS-rebinding double-resolution + `_PinnedIPAdapter`** pinning the validated IP while preserving TLS SNI/cert verification (closes validate-vs-connect TOCTOU); **redirects manually followed with per-hop re-validation**, bounded 5 hops.

**Auth/crypto:** API keys compared with `hmac.compare_digest`; stored only as keyed HMAC-SHA256 (never plaintext); no hardcoded default (falls back to `secrets.token_urlsafe(32)`); fail-closed on backend error; keys never logged.

**CSRF:** dual defense — global Origin/Referer middleware (exact-match, reject-on-missing) + per-endpoint double-submit token; tokens via `secrets.token_urlsafe(32)`, validated with `secrets.compare_digest`, per-user-bound, TTL/expiry.

**RBAC:** admin routes gate on `verify_role(Role.ADMIN)`; self-service key routes scoped to caller `user_id` with explicit IDOR protection on `revoke`.

**Agent:** no code/command execution or dynamic import from user/LLM output; crawled content never drives tool selection (hardcoded 3-tool allowlist); resource bounds on query length, result counts, crawl depth, token budgets, streamed response size; regexes reviewed — no ReDoS; PII HMAC-hashed before logging, URLs redacted, memory contents bypass the LLM.

**OSINT:** API keys sent via headers/`auth=`, never in URLs; `sanitize_url_for_logging`/`sanitize_exception_message` redact key-like params; breach sources log status codes only; HTML parsed with `html5lib`/`html.parser` (XXE-immune); MD5/SHA1 only for HIBP-style lookup hashes with `usedforsecurity=False`.

**Config/secrets:** Fernet (authenticated) encryption at rest; `.env`/`.encryption_key` created `0o600`; audit redaction of passwords/tokens/secrets/cookies; no committed secrets (`config/social_intel_config.json` ships empty `api_keys`); `.gitignore` covers `.env`/`.encryption_key`/`*.key`/`secret_scan_report.txt`.

**Infra/CI:** systemd unit runs non-root `www-data` with `NoNewPrivileges`/`ProtectSystem=strict`/`ProtectHome`/`PrivateTmp`/tight `ReadWritePaths`, no inline secrets; no `pull_request_target`; least-privilege `GITHUB_TOKEN`; third-party action pinned to full SHA; thorough dependency pinning to CVE-patched versions with documented references (urllib3, cryptography, aiohttp, lxml≥6.1.0 for XXE, starlette, etc.).

---

## Recommended Priority Order

1. **#1 DEV_MODE bind bypass** — highest real-world blast radius; add per-request loopback enforcement.
2. **#2, #3 file permissions** — quick, high-value fixes for local PII/key exposure.
3. **#6 github_source.py** — one-line concrete code fix; mirror sibling sources.
4. **#4, #5 agent injection/XSS** — confirm frontend escaping, lean on structural trust markers.
5. **#7, #8 CORS/rate-limit** — defense-in-depth for misconfiguration & brute-force.
6. **#14 SAST branch filters** — restore automated scanning coverage.
