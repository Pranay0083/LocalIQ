# 06 · Testing and Evaluation

Two automated layers: a **golden dataset** that pins the rubric and checks stored reports, and a
**pytest suite** that exercises the HTTP API of a running backend. A log of the manual QA passes
from the earlier hosted build is kept at the end as history.

## Status today

Measured against the local setup (MongoDB in Docker, backend on :8001) with no LLM and no
Razorpay keys in `backend/.env`:

| Suite | Result |
|---|---|
| Golden evals | **66 / 66** passed (dataset version 2026-06-08) |
| pytest | 82 collected · **73 passed · 9 failed** |

The 9 failures need real keys, not code changes: 7 tests assert on LLM output or on non-zero cost
metering, so they need a working LLM key; 2 need Razorpay test keys to create orders.

---

## 1 · Golden dataset (`backend/app/evals/golden.json`)

Deterministic: no LLM calls and no external network. The `production` suite reads the 25 most
recent reports from MongoDB.

```bash
cd backend
.venv/bin/python scripts/run_evals.py          # prints per-suite totals, writes test_reports/evals_golden_<stamp>.json
.venv/bin/python scripts/run_evals.py --quiet  # write only
```

The same run is available as `GET /api/evals/golden` and from the **Run checks now** button on
`/app/trust`; `GET /api/evals/dataset` returns the dataset itself. `scripts/run_evals.py` exits
non-zero when any check fails. Output goes to `test_reports/` at the repo root, which git ignores
(`*.json`); `project/reports/evals_golden_latest.json` is a copy of one such run.

### What is in the dataset

| Section | Contents |
|---|---|
| `fixtures` | 3 hand-written localities: **dense_urban** (metro at 900 m, dense amenity mesh, Satisfactory air), **sparse_suburb** (no metro within 6 km, thin mesh, Moderate air), **no_data** (nothing collected) |
| `expected_scores` | frozen module scores: 7 on dense_urban, 16 on sparse_suburb |
| `expected_absent` | modules that must report absence: 4 on dense_urban, 4 on sparse_suburb, all 20 on no_data |
| `invariants` | 13 cross-fixture relations, e.g. dense beats sparse on commute, sparse beats dense on noise |
| `arithmetic` | 7 boundary cases for `saturating`, `distance_score` and `aqi_to_score`, including `None` |
| `cpcb` | 3 pollutant sets with the expected AQI, dominant pollutant and band |
| `saturation_constants` | the calibrated `K` values the rubric must still use |
| `persona_modules` | the modules each of the 6 personas must and must not select |
| `block_contract` | the 8 render-block types (`gauge`, `trend_line`, `stat_grid`, `distance_list`, `incident_list`, `quote_list`, `timeline`, `text_block`) and the data keys the UI needs from each |

### The six suites

| Suite | Checks | What it protects |
|---|---|---|
| `arithmetic` | 9 | scoring primitives, monotonicity, calibrated saturation constants |
| `air` | 3 | CPCB worst-sub-index conversion and band labels |
| `scoring` | 26 | frozen module scores and absence handling on the three fixtures |
| `invariants` | 14 | the 13 relations plus determinism across repeated runs |
| `persona` | 8 | module selection per persona; weighting moves the composite by at least 3 points; the baseline computes |
| `production` | 6 | rules applied to the 25 most recent stored reports |
| **Total** | **66** | |

### The production suite

1. Every render block matches the UI contract.
2. Every `media`, `official` or `forum` citation has a source URL.
3. No module has a score without at least one citation.
4. An empty module never carries a score.
5. No anonymous post has status `corroborated` or `verified`.
6. Every stored card maps to a known rubric module.

Check 3 is why `presenter.present()` gives the derived `investment` module the citations of
`infrastructure` and `commute`, and `safety_night` those of `safety_day`, when they have none of
their own. A scored card with no citation would fail it.

---

## 2 · API test suite (`backend/tests/`, 82 tests)

The tests call a running backend over HTTP with `requests`; they do not use an in-process client.
The base URL comes from `REACT_APP_BACKEND_URL` in the environment, or from `frontend/.env`.
`pytest.ini` runs them on 2 xdist workers with `--dist loadscope`, so each test class or module
stays on one worker. The suite writes to the database it runs against (test users, reports, posts
and chat turns), so run it against a development database.

```bash
cd backend
.venv/bin/python -m pytest tests -q            # backend must be running on :8001
.venv/bin/python -m pytest tests -q -n 0       # serially
```

| File | Tests | Covers |
|---|---|---|
| `test_auth.py` | 7 | login (good and bad password), `/me` with and without a token, register then logout, profile update |
| `test_catalog.py` | 9 | locality list and search by name, pincode and zone; personas; modules; rubric; entitlement for Pro and free |
| `test_reports.py` | 5 | fetch a report, bad id, another user's report is `404`, chat history, a repeat `/generate` does not spend a report |
| `test_lens_and_chat.py` | 5 | lens switch spends no credit, unknown persona, grounded chat answer, SSE stream, stream ownership |
| `test_streaming_adversarial.py` | 5 | SSE headers and frames with a check that `###SOURCES###` never reaches the client, rent honesty, ownership `404`, auth, multi-turn context |
| `test_share.py` | 7 | token minted once, cannot share another user's report, auth, public read, teaser capped and cited, no owner data leaked, dead link `404` |
| `test_community.py` | 9 | public list and filter, leaderboard, PII scrub, fact claims need proof, short body rejected, repeat vote `409`, switching a vote |
| `test_contribute_and_evals.py` | 19 | link minting and listing, public page, bad tokens, PII scrub, proof type check, anonymous posts stay unverified, golden evals and dataset endpoints, compare paywall, lens switch |
| `test_premium_gating.py` | 3 | compare `402` on a free plan, unknown slug, second free recommendation gated |
| `test_billing.py` | 4 | plans, Razorpay order creation, bad plan, bad signature |
| `test_run_cost.py` | 7 | cost block populated, non-zero when an LLM ran, model priced at the published rates, a chat call is metered, run ledger scoped per run, `/traces` needs auth |
| `test_traces.py` | 1 | `/api/traces` shape |
| `test_evals.py` | 1 | golden evals all pass |

---

## 3 · What automated tests do not cover

- **Narrative quality** is not graded by a judge. The synthesizer is constrained by its prompt and
  by receiving only scores and drivers; the code checks only that a JSON object came back.
- **Payments** run in Razorpay test mode. Signature verification is tested; a real settlement is
  not.
- **External sources** are not mocked. When Overpass, OpenWeather or a publisher is down, a cold
  run collects fewer facts and the report shows those modules as absent.
- **Load and concurrency** have not been measured beyond the per-run ledger isolation test.
- **Frontend** has no automated tests; the screenshots in [07](07-screens.md) are the visual check.

## 4 · Known behaviour found while documenting

These come from reading the code. Each is current behaviour, not a test failure.

| Behaviour | Where |
|---|---|
| `/lens` reruns the synthesizer and refreshes stale layers; it is free of credit, not of LLM calls | `routers/reports.py`, `switch_lens()` |
| A keyless run reports `model: none — served from cache` because failed calls record no usage | `agents/graph.py`, `run_report()` |
| The per-IP contribution cap only applies when a proxy sets `X-Forwarded-For`; run directly, only the per-link cap applies | `routers/contribute.py`, `_ip_hash()` |
| Anonymous posts count toward the polarity of a claim group once two account holders have made the claim | `agents/collectors.py`, `collect_community()` |
| The rubric text for `safety_day` mentions a community signal, but `score_all()` does not read community claims for safety | `rubric_doc.py`, `agents/scorer.py` |

## 5 · Manual QA log (earlier hosted build)

Seven manual QA passes were run on the earlier hosted deployment. They have not been repeated on
the local setup and are kept as history.

| # | Focus | Result recorded then |
|---|---|---|
| 1 | Auth, generation, report, community, billing | 41/41 backend · 1 UI bug fixed |
| 2 | Light and dark theme, responsiveness, LLM provider switch | all pass |
| 3 | Backfilled data, adversarial citation traceability | 41/41 · 2 minor notes |
| 4 | Streaming chat, attempts to leak the protocol marker | 47/47 |
| 5 | Public share links | 54/54 · 1 UI bug (`ModuleCard readOnly`) fixed |
| 6 | Run-cost ledger | 62/63 (1 network timeout) |
| 7 | Contribution links, chat chips, golden evals | 18/18 |
