"""
scratch/test_rag_flow.py — Test the On-Demand RAG workflow.
1. Populate mock LTM.
2. Call _handle_memory_tool.
3. Validate history injection.
"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from vibehack.memory.db import record_experience, init_memory
from vibehack.core.repl.logic import _handle_memory_tool

class MockREPL:
    def __init__(self):
        self.history = []
    def _persist(self):
        pass

def test_rag():
    print("🚀 Initializing test DB...")
    init_memory()
    
    # 1. Record a fake successful experience
    print("📝 Recording mock experience...")
    record_experience(
        target="http://test-target.local",
        tech="nginx",
        payload="nmap -p80 --script http-enum",
        score=1,
        summary="Successfully discovered hidden /admin endpoint on Nginx."
    )
    
    # 2. Setup mock REPL
    repl = MockREPL()
    
    # 3. Trigger AI-style search command
    print("🔍 Simulating AI call: 'vibehack-memory search nginx'")
    _handle_memory_tool(repl, "vibehack-memory search nginx")
    
    # 4. Verify results
    print("\n📬 Resulting History Entry:")
    if repl.history:
        last_msg = repl.history[-1]
        print(f"Role: {last_msg['role']}")
        print(f"Content:\n{last_msg['content']}")
        
        if "Successfully discovered hidden /admin" in last_msg['content']:
            print("\n✅ TEST PASSED: Memory retrieved and injected successfully.")
        else:
            print("\n❌ TEST FAILED: Memory not found in feedback.")
    else:
        print("\n❌ TEST FAILED: History was not updated.")

if __name__ == "__main__":
    test_rag()
