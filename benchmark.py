import time
import re
from vibehack.guardrails.regex_engine import check_command

def run_benchmark():
    # Warm up
    for _ in range(100):
        check_command("nmap -sV -p 80 localhost")

    start_time = time.time()

    # Run a lot of times for a safe command (which hits all patterns)
    for _ in range(100000):
        check_command("nmap -sV -p 80 localhost")

    end_time = time.time()

    print(f"Time taken for 100000 check_command calls: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()
