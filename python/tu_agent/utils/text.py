import re

PASSED_RE = re.compile(r"(?P<n>\d+)\s+passed", re.IGNORECASE)
FAILED_RE = re.compile(r"(?P<n>\d+)\s+failed", re.IGNORECASE)
SKIPPED_RE = re.compile(r"(?P<n>\d+)\s+skipped", re.IGNORECASE)

def parse_pytest_pass_rate(output: str) -> float:
    """Best-effort parse of pytest summary.

    Returns:
      - pass rate in [0,1] if we can infer passed/failed counts
      - -1.0 if parsing fails
    """
    passed = 0
    failed = 0
    m = PASSED_RE.search(output)
    if m:
        passed = int(m.group("n"))
    m = FAILED_RE.search(output)
    if m:
        failed = int(m.group("n"))
    total = passed + failed
    if total <= 0:
        return -1.0
    return passed / total
