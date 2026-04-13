import time
import re
from vibehack.guardrails.regex_engine import DANGEROUS_PATTERNS

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]

def check_command_compiled(command: str, unchained: bool = False) -> str | None:
    if unchained:
        return None
    for pattern_obj in COMPILED_PATTERNS:
        if pattern_obj.search(command):
            return f"Blocked by guardrails (Pattern matched: {pattern_obj.pattern})"
    return None

def run_benchmark():
    # Warm up
    for _ in range(100):
        check_command_compiled("nmap -sV -p 80 localhost")

    start_time = time.time()

    # Run a lot of times for a safe command (which hits all patterns)
    for _ in range(100000):
        check_command_compiled("nmap -sV -p 80 localhost")

    end_time = time.time()

    print(f"Time taken for 100000 check_command_compiled calls: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()
