"""
Toolkit Security Module - Auto-provisioning and CVE intelligence.

Submodules:
- security_tools: Auto-install pentesting tools
- cve_lookup: Real-time CVE intelligence
"""

from vibehack.toolkit.security.security_tools import (
    is_tool_available,
    install_tool,
    install_tools_batch,
    ensure_tools,
    check_tool_availability,
    SECURITY_TOOLS,
    install_common_tools,
    get_missing_tools,
)

from vibehack.toolkit.security.cve_lookup import (
    CVEIntelligence,
    get_cve_intelligence,
    get_cve_context,
)

__all__ = [
    "is_tool_available",
    "install_tool",
    "install_tools_batch",
    "ensure_tools",
    "check_tool_availability",
    "SECURITY_TOOLS",
    "install_common_tools",
    "get_missing_tools",
    "CVEIntelligence",
    "get_cve_intelligence",
    "get_cve_context",
]
