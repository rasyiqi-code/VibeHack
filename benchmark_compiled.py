import time
import ctypes
from vibehack.guardrails.regex_engine import check_command

def run_benchmark_compiled():
    # Performance testing using a neutral network check command.
    test_cmd = "curl --head --user-agent 'VibeHack-Audit' http://localhost:8080"

    # Warm up
    for _ in range(100):
        check_command(test_cmd)

    start_time = time.time()

    # Intensive stress-test for the guardrail engine
    for _ in range(100000):
        check_command(test_cmd)

    end_time = time.time()

    print(f"Time taken for 100000 check_command calls (compiled context): {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    run_benchmark_compiled()
