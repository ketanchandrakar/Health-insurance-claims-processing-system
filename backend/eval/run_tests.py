#!/usr/bin/env python3
"""
HTTP test runner against the live /claims/evaluate endpoint.

Reads test_cases.json, injects fixtures + _today override per case,
sends each as a POST request, and reports pass/fail against expected.

Usage (from backend/):
    python eval/run_tests.py
    python eval/run_tests.py --url http://localhost:8000   # default
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).parent.parent
TC_FILE = ROOT / "data" / "test_cases.json"
FIXTURES_DIR = ROOT / "fixtures"

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"


def load_fixture(case_id: str) -> dict:
    path = FIXTURES_DIR / f"{case_id.lower()}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def clean_documents(raw_docs: list[dict]) -> list[dict]:
    """Keep only DocumentInput fields; add file_name if missing."""
    result = []
    for doc in raw_docs:
        result.append({
            "file_id": doc["file_id"],
            "file_name": doc.get("file_name", f"{doc['file_id'].lower()}.jpg"),
            "actual_type": doc.get("actual_type"),
        })
    return result


def check(expected: dict, response: dict) -> list[str]:
    """Return list of failure strings; empty list = pass."""
    failures = []

    exp_decision = expected.get("decision")
    if exp_decision is not None:
        got = response.get("status")
        if got != exp_decision:
            failures.append(f"status: expected {exp_decision!r}, got {got!r}")

    exp_amount = expected.get("approved_amount")
    if exp_amount is not None:
        got = response.get("approved_amount")
        if got != float(exp_amount):
            failures.append(f"approved_amount: expected {exp_amount}, got {got}")

    for r in expected.get("rejection_reasons", []):
        if r not in response.get("rejection_reasons", []):
            failures.append(f"rejection_reasons: missing {r!r}")

    conf_spec = expected.get("confidence_score", "")
    if conf_spec:
        got_conf = response.get("confidence", 0)
        if conf_spec.startswith("above "):
            threshold = float(conf_spec.split()[1])
            if got_conf <= threshold:
                failures.append(f"confidence: expected > {threshold}, got {got_conf}")
        elif "below " in conf_spec or "< " in conf_spec:
            threshold = float(conf_spec.split()[-1])
            if got_conf >= threshold:
                failures.append(f"confidence: expected < {threshold}, got {got_conf}")

    return failures


def run(base_url: str = BASE_URL) -> None:
    data = json.loads(TC_FILE.read_text(encoding="utf-8"))
    cases = data["test_cases"]
    total = len(cases)
    passed = 0

    print(f"\nRunning {total} test cases against {base_url}\n")

    for tc in cases:
        case_id: str = tc["case_id"]
        name: str    = tc["case_name"]
        inp: dict    = tc["input"]
        expected: dict = tc["expected"]

        body: dict = {k: v for k, v in inp.items() if k != "documents"}
        body["documents"] = clean_documents(inp.get("documents", []))

        fixture = load_fixture(case_id)
        if fixture:
            body["_fixtures"] = fixture

        treat = date.fromisoformat(str(inp["treatment_date"]))
        body["_today"] = (treat + timedelta(days=5)).isoformat()

        try:
            resp = requests.post(f"{base_url}/claims/evaluate", json=body, timeout=30)
            response = resp.json()
        except Exception as exc:
            print(f"  {RED}❌ [{case_id}]{RESET} {name}")
            print(f"     REQUEST ERROR: {exc}\n")
            continue

        failures = check(expected, response)
        ok = not failures
        if ok:
            passed += 1

        icon = f"{GREEN}✅{RESET}" if ok else f"{RED}❌{RESET}"
        status_val = response.get("status", "?")
        amount_val = response.get("approved_amount")
        conf_val   = response.get("confidence")

        print(f"  {icon} [{case_id}] {name}")
        print(f"     status={status_val}  amount={amount_val}  confidence={conf_val}")
        for f in failures:
            print(f"     {RED}FAIL:{RESET} {f}")
        if not ok:
            for event in response.get("trace", []):
                if event.get("component") == "fraud":
                    print(f"     fraud_detail={event.get('detail')}")
        print()

    bar = "=" * 60
    colour = GREEN if passed == total else RED
    print(bar)
    print(f"  {colour}{passed}/{total} passed{RESET}")
    print(bar)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    url = BASE_URL
    if "--url" in sys.argv:
        idx = sys.argv.index("--url")
        url = sys.argv[idx + 1]
    run(url)
