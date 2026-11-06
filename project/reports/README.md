# Generated reports

Regenerate both with the commands in the project README.

| File | Source | Contents |
|---|---|---|
| `evals_golden_latest.json` | `python backend/run_evals.py` | Full golden run: 66 checks across 6 suites, per-check pass/fail with detail, persona sensitivity spread, dataset version |
| `app_stats.json` | `python project/scripts/collect_stats.py` | Live corpus counts, token + cost ledger totals, cost by locality, run-duration percentiles, community posts by status |

## Headline numbers at time of capture

| | |
|---|---|
| Golden checks | 66 / 66 passing |
| Backend tests | 82 collected in `backend/tests` |
| QA passes | 7, zero open defects |
| Agent runs recorded | 33 (30 costed) |
| Total LLM spend | $1.03 |
| Average per costed run | $0.034 |
| Median run time | 12.7 s warm · 165.5 s slowest cold run |
| Paid web searches | 0 |
