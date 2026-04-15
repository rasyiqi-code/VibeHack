"""
vibehack/toolkit/cve_lookup.py — Real-time CVE Intelligence.

Dynamically fetches CVE data for detected technologies.
Integrates with NVD API for latest vulnerability data.
"""

import json
import re
import httpx
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class CVEIntelligence:
    """
    Real-time CVE intelligence for discovered technologies.
    Uses NVD API for vulnerability data.
    """

    def __init__(self, cache_ttl_hours: int = 24):
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_file = "~/.vibehack/cve_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load CVE cache from disk."""
        import os
        from pathlib import Path
        from vibehack.config import cfg

        cache_path = Path.home() / ".vibehack" / "cve_cache.json"
        if not cache_path.exists():
            return {}

        try:
            with open(cache_path) as f:
                data = json.load(f)
                # Clean expired entries
                cleaned = {}
                for key, val in data.items():
                    if "timestamp" in val:
                        ts = datetime.fromisoformat(val["timestamp"])
                        if datetime.now() - ts < self.cache_ttl:
                            cleaned[key] = val
                    else:
                        cleaned[key] = val
                return cleaned
        except:
            return {}

    def _save_cache(self):
        """Save CVE cache to disk."""
        import os
        from pathlib import Path

        cache_path = Path.home() / ".vibehack" / "cve_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, "w") as f:
            json.dump(self._cache, f)

    async def get_cves_async(self, keyword: str, limit: int = 5) -> List[Dict]:
        """
        Fetch CVEs for a keyword asynchronously.
        Uses NVD API 2.0.
        """
        # Check cache first
        cache_key = f"{keyword}_{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key].get("cves", [])

        cves = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # NVD API 2.0 endpoint
                url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
                params = {
                    "keywordSearch": keyword,
                    "resultsPerPage": limit,
                    "startIndex": 0,
                }

                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    vulnerabilities = data.get("vulnerabilities", [])

                    for vuln in vulnerabilities:
                        cve_data = vuln.get("cve", {})
                        cve_id = cve_data.get("id", "")

                        # Extract description
                        descriptions = cve_data.get("descriptions", [])
                        desc = descriptions[0].get("value", "") if descriptions else ""

                        # Extract severity
                        metrics = cve_data.get("metrics", {})
                        cvss = metrics.get("cvssMetricV31", [])
                        severity = "UNKNOWN"
                        score = 0.0

                        if cvss:
                            cvss_data = cvss[0].get("cvssData", {})
                            severity = cvss_data.get("baseSeverity", "UNKNOWN")
                            score = cvss_data.get("baseScore", 0.0)

                        cves.append(
                            {
                                "id": cve_id,
                                "description": desc[:200],
                                "severity": severity,
                                "score": score,
                                "published": cve_data.get("published", ""),
                            }
                        )

                        if len(cves) >= limit:
                            break
        except Exception as e:
            pass  # Silent fail - don't block execution

        # Cache result
        self._cache[cache_key] = {"cves": cves, "timestamp": datetime.now().isoformat()}
        self._save_cache()

        return cves

    def get_cves(self, keyword: str, limit: int = 5) -> List[Dict]:
        """
        Synchronous wrapper for get_cves_async.
        """
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, self.get_cves_async(keyword, limit)
                    )
                    return future.result(timeout=15)
            else:
                return asyncio.run(self.get_cves_async(keyword, limit))
        except:
            return []

    def format_cve_context(self, technology: str) -> str:
        """
        Format CVE context string for prompt injection.
        Returns formatted string with top CVEs for technology.
        """
        cves = self.get_cves(technology, limit=3)

        if not cves:
            return f"\n### {technology}: No recent CVEs found\n"

        lines = [f"\n### {technology} - Recent Vulnerabilities:"]

        for cve in cves:
            severity_marker = (
                "🔴" if cve["score"] >= 9.0 else ("🟠" if cve["score"] >= 7.0 else "🟡")
            )
            lines.append(
                f"- {severity_marker} {cve['id']} (CVSS: {cve['score']}) - {cve['severity']}"
            )
            lines.append(f"  {cve['description'][:100]}...")

        return "\n".join(lines)


# Global instance
_cve_intel = None


def get_cve_intelligence() -> CVEIntelligence:
    """Get global CVE intelligence instance."""
    global _cve_intel
    if _cve_intel is None:
        _cve_intel = CVEIntelligence()
    return _cve_intel


def get_cve_context(technology: str) -> str:
    """Quick function to get CVE context."""
    return get_cve_intelligence().format_cve_context(technology)
