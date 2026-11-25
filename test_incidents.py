import json
import httpx

BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    cases = [json.loads(line) for line in open("sample_logs.jsonl", encoding="utf-8") if line.strip()]
    matched = 0
    total_ms = 0
    auto_verified = 0

    with httpx.Client(timeout=15.0) as client:
        for case in cases:
            res = client.post(
                f"{BASE_URL}/triage",
                json={"logs": case["logs"], "expected_cause": case["expected_cause"]},
            )
            res.raise_for_status()
            data = res.json()
            got = (data.get("root_cause") or "").strip().lower()
            exp = case["expected_cause"].strip().lower()
            is_match = exp in got or got in exp
            if is_match:
                matched += 1
            if data.get("verification_status") == "verified_safe_fix":
                auto_verified += 1
            total_ms += data.get("triage_ms", 0)
            print(
                f"[{case['id']}] match={is_match} | {data.get('triage_ms')}ms | "
                f"{data.get('verification_status')} | cause={data.get('root_cause')}"
            )

    n = len(cases)
    avg_ms = total_ms / n if n else 0
    print("\n--- Benchmark Summary ---")
    print(f"Root-Cause Accuracy : {matched}/{n} ({matched / n * 100:.1f}%)")
    print(f"Avg Triage Latency  : {avg_ms:.1f} ms")
    print(f"Auto-Verified Fixes : {auto_verified}/{n}")
    print(f"Human Escalations   : {n - auto_verified}/{n}")


if __name__ == "__main__":
    main()
