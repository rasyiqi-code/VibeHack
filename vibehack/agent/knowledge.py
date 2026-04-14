"""
vibehack/agent/knowledge.py — Goal-Oriented Knowledge State (PRD v1.8 §6.4).

Tracks WHAT THE AI KNOWS about the target — not what steps it has completed.
This is the difference between "ran scan" (task state) and
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
    mission_goals: List[str] = field(default_factory=list) # §6.x: Active mission goals

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
            "mission_goals": self.mission_goals,
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
            mission_goals=data.get("mission_goals", []),
        )

    def add_note(self, note: str):
        """Add a knowledge note, avoiding duplicates."""
        if note not in self.notes:
            self.notes.append(note)


# ── Auto-extraction from command output ───────────────────────────────────────

# Generic Port Recognition (Supports Nmap, Rustscan, Naabu, Masscan, etc.)
_PORT_GENERIC_1 = re.compile(r"(\d{1,5})/(tcp|udp)\s+(?:open|listening|up)", re.IGNORECASE)
_PORT_GENERIC_2 = re.compile(r"(?:open|found|port)\s+.*?(\d{1,5})(?:\s|:|$)", re.IGNORECASE)
_PORT_GENERIC_3 = re.compile(r"(\d{1,5}):\s*open", re.IGNORECASE)

# Universal Technology/Banner extraction pattern: Name/1.2.3 or Name 1.2.3
_GENERIC_TECH_BANNER = re.compile(r"([a-zA-Z0-9\-_]{3,})[/\s](\d+\.[\d\.a-z\-]+)", re.IGNORECASE)

# Endpoint patterns (URLs found in output)
_ENDPOINT_PATTERN = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH|Found|Status)\s+(\/[^\s\"']+)", re.IGNORECASE)
_URL_PATH_PATTERN = re.compile(r"https?://[^\s\"']+(/[^\s\"']*)", re.IGNORECASE)

# ── Universal Scanner Patterns ─────────────────────────────────────────
# Matches common pattern: [severity] [any-label] <target/url>
_SCANNER_FINDING = re.compile(r"\[(info|low|medium|high|critical)\] \[.*?\] ([^\s]+)", re.IGNORECASE)
# Matches common directory discovery: (Status: 200) | /endpoint
_DISCOVERY_PATH = re.compile(r"(?:\||Status:.*)\s+(\/[^\s]+)", re.IGNORECASE)

def extract_knowledge(output: str, knowledge: KnowledgeState) -> KnowledgeState:
    """Auto-extract knowledge from ANY shell command output."""
    if not output or len(output.strip()) < 5:
        return knowledge

    # 1. Ports (Universal)
    for p in [_PORT_GENERIC_1, _PORT_GENERIC_2, _PORT_GENERIC_3]:
        for m in p.finditer(output):
            try:
                port_num = int(m.group(1))
                if 1 <= port_num <= 65535:
                    knowledge.open_ports.add(port_num)
            except (ValueError, IndexError): continue

    # 2. Technologies (Universal Dynamic Discovery)
    # Check headers first (highest confidence)
    server_match = re.search(r"Server:\s+([a-zA-Z0-9\-_]+)", output, re.IGNORECASE)
    if server_match:
        knowledge.technologies.add(server_match.group(1).lower())
    powered_match = re.search(r"X-Powered-By:\s+([a-zA-Z0-9\-_]+)", output, re.IGNORECASE)
    if powered_match:
        knowledge.technologies.add(powered_match.group(1).lower())

    # Generic Banner matching (extracts 'Name' from 'Name/Version' or 'Name Version')
    for m in _GENERIC_TECH_BANNER.finditer(output):
        tech_name = m.group(1).lower()
        # Filter out common false positives if necessary, or just trust the pattern
        if tech_name not in ["http", "tcp", "udp", "port"]:
            knowledge.technologies.add(tech_name)
            knowledge.add_note(f"Detected {tech_name} version {m.group(2)}")

    # 3. Endpoints & Findings (Generic)
    seen_endpoints = set(knowledge.endpoints)
    for m in _ENDPOINT_PATTERN.finditer(output):
        ep = m.group(1)
        if ep not in seen_endpoints and len(ep) < 120:
            knowledge.endpoints.append(ep)
            seen_endpoints.add(ep)
            
    for m in _SCANNER_FINDING.finditer(output):
        knowledge.add_note(f"Finding [{m.group(1)}]: {m.group(2)}")
        
    for m in _DISCOVERY_PATH.finditer(output):
        ep = m.group(1)
        if ep not in seen_endpoints and len(ep) < 120:
            knowledge.endpoints.append(ep)
            seen_endpoints.add(ep)

    # Trim to reasonable size
    knowledge.endpoints = knowledge.endpoints[:100]

    return knowledge
