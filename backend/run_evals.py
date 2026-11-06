"""CLI: run the golden evaluation and write the report to test_reports/ at the repo root.

    python3 run_evals.py                 # print summary, write dated report
    python3 run_evals.py --quiet         # write only
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from app.evals.runner import run_golden

OUT_DIR = Path(__file__).resolve().parent.parent / "test_reports"


async def main():
    result = await run_golden()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"evals_golden_{stamp}.json"
    path.write_text(json.dumps(result, indent=2))

    summary = result["summary"]
    if "--quiet" not in sys.argv:
        for suite, stats in summary["suites"].items():
            print(f"{suite:<22} {stats['passed']}/{stats['total']}")
        for row in result["results"]:
            if row["status"] == "fail":
                print(f"  FAIL [{row['suite']}] {row['check']} :: {row['detail']}")
    print(f"\n{summary['passed']}/{summary['total']} passed · dataset {result['dataset_version']} "
          f"· written to {path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
