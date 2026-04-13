import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

class EvidenceManager:
    """
    Handles the physical collection of attack evidence (logs, PoCs, and outputs).
    This is what separates a tool from a professional auditing framework.
    """
    def __init__(self, session_id: str):
        from vibehack.config import cfg
        self.session_id = session_id
        self.base_dir = cfg.HOME / "sessions" / session_id / "evidence"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def capture(self, title: str, command: str, output: str) -> str:
        """
        Saves the raw command and its output specifically as a proof of vulnerability.
        """
        # Create a filesystem-friendly filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        filename = f"PoC_{clean_title}_{datetime.now().strftime('%H%M%S')}.txt"
        filepath = self.base_dir / filename

        content = [
            f"VIBEHACK EVIDENCE [Session: {self.session_id}]",
            f"Timestamp: {datetime.now().isoformat()}",
            f"Vulnerability: {title}",
            "=" * 60,
            f"EXECUTION CONTEXT:",
            f"Command: {command}",
            "-" * 60,
            f"RAW TERMINAL OUTPUT:",
            output,
            "=" * 60,
            "\n[End of Evidence Block]"
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

        return str(filepath)

    def save_poc_script(self, title: str, poc_code: str, ext: str = "sh"):
        """Saves a standalone reproduction script."""
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        filename = f"repro_{clean_title}.{ext}"
        filepath = self.base_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(poc_code)
            
        return str(filepath)
