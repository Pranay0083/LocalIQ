# 06 · Testing & Evaluation

Three independent layers: a **golden dataset** for the rubric, a **pytest suite** for the API, and
**seven QA passes** for end-to-end behaviour.

---

## 1 · Golden dataset (`backend/app/evals/golden.json`)

Deterministic. No LLM calls, no network. Safe on every deploy.

```bash
cd backend && python run_evals.py              # CLI, writes test_reports/evals_golden_*.json
GET /api/evals/golden                            # same run, live
GET /api/evals/dataset                           # the dataset itself
/app/trust → "Run checks now"                    # in-product
```

### What is in the dataset

| Section | Contents |
|---|---|
| `fixtures` | 3 hand-written localities: **dense_urban** (metro at 900 m, dense mesh, Satisfactory air), **sparse_suburb** (no metro within 6 km, thin mesh, Moderate air), **no_data** (cold start, nothing collected) |
| `expected_scores` | Frozen module scores — 7 hand-computed on dense_urban, 16 regression-locked on sparse_suburb |
| `expected_absent` | Modules that must report absence rather than a number (all 20 for `no_data`) |
| `invariants` | 13 cross-fixture relations, e.g. dense > sparse on commute, sparse > dense on noise |
| `arithmetic` | `saturating`, `distance_score`, `aqi_to_score` boundary cases incl. `None` handling |
| `cpcb` | 3 pollutant sets → expected AQI, dominant pollutant and band |
| `persona_modules` | Per-persona module inclusion/exclusion matrix |
| `block_contract` | The 8 render-block types and the data keys the UI requires from each |

### The six suites

| Suite | Checks | What it protects |
|---|---|---|
| `arithmetic` | 9 | scoring primitives, monotonicity, calibrated saturation constants |
| `air` | 3 | CPCB worst-sub-index conversion and band labelling |
| `scoring` | 26 | frozen module scores + absence handling on all three fixtures |
| `invariants` | 14 | relational sanity + determinism across repeated runs |
| `persona` | 8 | module selection per persona, weighting actually moves the composite (spread ≥ 3) |
| `production` | 6 | the same rules applied to the 25 most recent **stored** reports |
| **Total** | **66** | |

### The production suite (this is the one that finds real bugs)

1. Every render block matches the UI contract.
2. Every media/official claim carries a source URL.
3. **No scored module without a citation behind it.**
4. An empty module never carries a score.
5. An anonymous contribution can never reach `verified` or `corroborated`.
6. Every stored card maps to a known rubric module.

> **It earned its keep on day one.** Check 3 failed on first run: `investment` is a *derived* module
> (blended from infrastructure + commute) and was rendering a score with zero citations — a hole in
> the trust layer that no unit test would have caught. Presenter now inherits the source citations,
> and the four affected stored reports were backfilled. **Current: 66/66.**

---

## 2 · Backend test suite (`backend/tests/`, 82 tests)

Runs over HTTP against a running backend (`REACT_APP_BACKEND_URL`), not an in-process client.

```bash
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest tests -q
```

| File | Covers |
|---|---|
| `test_auth.py` | register, login, brute force, JWT, profile |
| `test_catalog.py` | localities, personas, modules, rubric |
| `test_reports.py` | generation, job trace, ownership, caching branch |
| `test_lens_and_chat.py` | free lens switching, grounded chat, history |
| `test_streaming_adversarial.py` | SSE integrity, `###SOURCES` marker never leaks |
| `test_share.py` | share token minting, public teaser, dead links |
| `test_community.py` | posting, PII scrub, proof, voting, credits |
| `test_contribute_and_evals.py` | contribution links, anonymous publishing, eval endpoints |
| `test_premium_gating.py` | 402 paywall for compare, recommendation free run |
| `test_billing.py` | Razorpay order + signature verification (test mode) |
| `test_run_cost.py` | ledger arithmetic, per-run isolation, metering, schema |
| `test_traces.py` | trace endpoint shape |
| `test_evals.py` | golden runner shape |

---

## 3 · QA passes

| # | Focus | Result |
|---|---|---|
| 1 | First full pass — auth, generation, report, community, billing | 41/41 backend · 1 UI bug found & fixed |
| 2 | Light/dark theme, responsiveness, LLM provider switch | all pass |
| 3 | Post-backfill data + **adversarial citation traceability** | 41/41 · 2 minor notes |
| 4 | Streaming chat, adversarial marker-leak attempts | 47/47 |
| 5 | Public share links | 54/54 · 1 UI bug (`ModuleCard readOnly`) fixed |
| 6 | Run-cost ledger correctness | 62/63 (1 transient network timeout) |
| 7 | Contribution links · chat chips · golden evals | 18/18 executed · **0 defects on new work** |

### Known, accepted findings

| Finding | Status |
|---|---|
| Two seeded demo reports show `cost: not recorded` | Accepted — they predate the ledger. Honest, not wrong. |
| `pro@localiq.in` hits the 100 msg/day chat cap during testing | Expected behaviour — tests use a throwaway account |
| `429` from the contribution endpoint during bulk testing | Expected — the per-IP quota working as designed |

---

## 4 · What is *not* covered by automated tests

Stated plainly, because a test report that overclaims is worse than no test report:

- **LLM output quality** is not scored by a judge. The narrative is constrained by schema and by the
  facts in the prompt, and the adversarial suite checks it cannot leak protocol markers — but nobody
  is grading the prose.
- **Razorpay is in test mode.** Signature verification is tested; a real settlement is not.
- **External source availability** is not mocked. If Overpass or a publisher is down, a cold run
  degrades to fewer facts — which the report renders as an explicit gap, by design.
- **Load and concurrency** beyond per-run cost isolation have not been measured.
