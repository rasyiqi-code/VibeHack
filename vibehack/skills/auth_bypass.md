# Skill: Authentication Bypass & JWT Patterns
# Trigger: jwt, auth, login, .js, bearer

### Phase 1: JWT Analysis
- Check for `alg: none` vulnerability.
- Attempt to crack weak secret keys using `hashcat -m 16500` or `jwt-pwn`.
- Check for RS256 to HS256 "Key Confusion" attack.
- Look for `kid` (Key ID) injection: target files like `/dev/null` or SQL injection in `kid`.

### Phase 2: OAuth/OAuth2 Logic
- Redirect URI manipulation: try `https://attacker.com` or `https://victim.com.attacker.com`.
- State parameter bypass cross-site request forgery.
- Look for token leakage in referer headers.

### Phase 3: Cookie Stealing & Session Fixation
- Check if `HttpOnly` or `Secure` flags are missing.
- Try session fixation by providing a fixed session ID during login.
