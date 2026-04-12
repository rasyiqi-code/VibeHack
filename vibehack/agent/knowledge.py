"""
vibehack/agent/knowledge.py — Goal-Oriented Knowledge State (PRD v1.8 §6.4).

Tracks WHAT THE AI KNOWS about the target — not what steps it has completed.
This is the difference between "ran nmap" (task state) and
"ports 80, 443, 8080 are open running nginx/1.18" (knowledge state).

The KnowledgeState is:
  - Built incrementally from command outputs (auto-extracted)
  - Injected into the system prompt each turn
  - Persisted in session JSON
  - Used by the AI to make goal-oriented decisions
"""
import re
from dataclasses import dataclass, field
from typing import Set, List, Optional


@dataclass
class KnowledgeState:
    """Structured knowledge about the target accumulated during the session."""
    open_ports: Set[int] = field(default_factory=set)
    technologies: Set[str] = field(default_factory=set)
    endpoints: List[str] = field(default_factory=list)
    credentials: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    tested_surfaces: Set[str] = field(default_factory=set)

    def is_empty(self) -> bool:
        return not any([
            self.open_ports, self.technologies, self.endpoints,
            self.credentials, self.notes,
        ])

    def to_dict(self) -> dict:
        return {
            "open_ports": sorted(self.open_ports),
            "technologies": sorted(self.technologies),
            "endpoints": self.endpoints[:50],
            "credentials": self.credentials,
            "notes": self.notes[-20:],
            "tested_surfaces": sorted(self.tested_surfaces),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeState":
        return cls(
            open_ports=set(data.get("open_ports", [])),
            technologies=set(data.get("technologies", [])),
            endpoints=data.get("endpoints", []),
            credentials=data.get("credentials", []),
            notes=data.get("notes", []),
            tested_surfaces=set(data.get("tested_surfaces", [])),
        )

    def add_note(self, note: str):
        """Add a knowledge note, avoiding duplicates."""
        if note not in self.notes:
            self.notes.append(note)


# ── Auto-extraction from command output ───────────────────────────────────────

# Port patterns: nmap, rustscan, naabu output
_PORT_NMAP = re.compile(r"(\d{1,5})/tcp\s+open", re.IGNORECASE)
_PORT_RUSTSCAN = re.compile(r"Open .*?:(\d{1,5})", re.IGNORECASE)
_PORT_GENERIC = re.compile(r"\bport[s]?\s+(\d{1,5})\s+(?:open|listening)", re.IGNORECASE)

# Technology fingerprints (server headers, banner grabs, etc.)
TECH_FINGERPRINTS: dict[str, re.Pattern] = {
    "nginx":       re.compile(r"nginx[/\s]", re.IGNORECASE),
    "apache":      re.compile(r"apache[/\s]", re.IGNORECASE),
    "express":     re.compile(r"Express|node\.?js", re.IGNORECASE),
    "django":      re.compile(r"django|wsgi", re.IGNORECASE),
    "flask":       re.compile(r"Werkzeug|flask", re.IGNORECASE),
    "spring":      re.compile(r"Spring[- ]Boot|java", re.IGNORECASE),
    "wordpress":   re.compile(r"wp-content|wp-login|WordPress", re.IGNORECASE),
    "laravel":     re.compile(r"laravel|php artisan", re.IGNORECASE),
    "rails":       re.compile(r"Ruby on Rails|Passenger", re.IGNORECASE),
    "asp.net":     re.compile(r"ASP\.NET|IIS/", re.IGNORECASE),
    "fastapi":     re.compile(r"FastAPI|uvicorn", re.IGNORECASE),
    "tomcat":      re.compile(r"Apache Tomcat|Catalina", re.IGNORECASE),
    "iis":         re.compile(r"Microsoft-IIS", re.IGNORECASE),
    "grafana":     re.compile(r"Grafana", re.IGNORECASE),
    "jenkins":     re.compile(r"Jenkins|Hudson", re.IGNORECASE),
    "kubernetes":  re.compile(r"kubernetes|k8s|kubectl", re.IGNORECASE),
    "docker":      re.compile(r"Docker|container", re.IGNORECASE),
    "mysql":       re.compile(r"MySQL|MariaDB", re.IGNORECASE),
    "postgresql":  re.compile(r"PostgreSQL|psql", re.IGNORECASE),
    "mongodb":     re.compile(r"MongoDB|mongod", re.IGNORECASE),
    "redis":       re.compile(r"Redis", re.IGNORECASE),
    "openssh":     re.compile(r"OpenSSH", re.IGNORECASE),
}

# Endpoint patterns (URLs found in output)
_ENDPOINT_PATTERN = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH|Found|Status)\s+(\/[^\s\"']+)", re.IGNORECASE)
_URL_PATH_PATTERN = re.compile(r"https?://[^\s\"']+(/[^\s\"']*)", re.IGNORECASE)


def extract_knowledge(output: str, knowledge: KnowledgeState) -> KnowledgeState:
    """
    Auto-extract knowledge from shell command output and merge into KnowledgeState.
    Returns the same object (mutated in-place) for chaining.
    """
    if not output or len(output.strip()) < 5:
        return knowledge

    # ── Ports ─────────────────────────────────────────────────────────────
    for m in _PORT_NMAP.finditer(output):
        knowledge.open_ports.add(int(m.group(1)))
    for m in _PORT_RUSTSCAN.finditer(output):
        knowledge.open_ports.add(int(m.group(1)))
    for m in _PORT_GENERIC.finditer(output):
        knowledge.open_ports.add(int(m.group(1)))

    # ── Technologies ──────────────────────────────────────────────────────
    for tech, pattern in TECH_FINGERPRINTS.items():
        if pattern.search(output):
            knowledge.technologies.add(tech)

    # ── Endpoints ─────────────────────────────────────────────────────────
    seen_endpoints = set(knowledge.endpoints)
    for m in _ENDPOINT_PATTERN.finditer(output):
        ep = m.group(1)
        if ep not in seen_endpoints and len(ep) < 120:
            knowledge.endpoints.append(ep)
            seen_endpoints.add(ep)
    for m in _URL_PATH_PATTERN.finditer(output):
        ep = m.group(1)
        if ep not in seen_endpoints and len(ep) < 120:
            knowledge.endpoints.append(ep)
            seen_endpoints.add(ep)

    # Trim to reasonable size
    knowledge.endpoints = knowledge.endpoints[:100]

    return knowledge
