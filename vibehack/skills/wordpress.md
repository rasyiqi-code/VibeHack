# Specialized Tactics: WordPress Security Auditing
Aliases: wp, wordpress, wp-cms

- **Nonce Extraction**: Sensitive REST API actions often require a cryptographic nonce. Search for '_wpnonce' or 'wpApiSettings' in the raw HTML of the homepage or login pages to authorize your requests.
- **REST API Mapping**: Do not guess routes. Fetch the `wp-json/` root directory to map all available namespaces and internal routes (e.g., searching for custom theme endpoints like 'wpmedia/v1').
- **Client-Side Logic Analysis**: Extract and analyze JavaScript files in theme (`wp-content/themes/`) or plugin directories. Look for hardcoded keys, hidden API parameters, or legacy debugging flags.
- **WAF Adaptation (Hostinger/HCDN)**: If you face consistent 403 or 404 errors during fuzzing, assume an active WAF. Switch to passive enumeration, metadata analysis, or search for exposed backup files (`.bak`, `.zip`, `.env`).
- **XML-RPC Exploitation**: If `xmlrpc.php` is available, check for `system.multicall` to batch requests or `pingback.ping` for internal SSRF/scanning.
