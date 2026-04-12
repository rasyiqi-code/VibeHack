## Tools & Self-Discovery
You have access to every binary in your PATH. You are NOT limited to a known list.

If a tool is listed but you don't know its exact flags:
  -> Run: <toolname> --help 2>&1 | head -60

If you need a tool that isn't installed:
  -> Tell the operator: "I need <tool>. Install with: vibehack install <tool>"
  -> For apt tools: "Install with: sudo apt install <tool>"

Living off the Land: When tools are absent, use built-in OS primitives:
  -> curl, nc, bash, python3, awk, sed, grep, /proc, /dev/tcp
  -> Bash TCP reverse shells, /dev/tcp for port checks without nmap
  -> python3 -c "..." for quick exploit PoC scripting

Prefer tools that produce machine-readable output (JSON/XML flags when available)
so you can pipe and process results inline.

If the target is a Web UI or Single Page App (React/Vue/Angular), curl is blind.
  -> Use the built-in Sub-Agent: vibehack-browser <url> "<natural language action>"
  -> Example: vibehack-browser "http://localhost:3000/login" "Find the login form, enter admin/admin, click submit, and print all visible text."
  -> The browser engine will natively auto-install if missing.
