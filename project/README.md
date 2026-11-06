# LocalIQ: project documentation

Neighbourhood quality reports for 34 Bengaluru localities. A report is weighted for one of six
personas, every scored module cites the data or page behind it, a module with no data is shown as
missing instead of being averaged, and the LLM spend of each run is metered.

| | |
|---|---|
| Stack | FastAPI, MongoDB (Motor), LangGraph · React 19, Tailwind, Recharts |
| Runs as | MongoDB in Docker, backend on :8001, frontend on :3000, all on one machine |
| Report graph | 9 LangGraph nodes: intake → 4 parallel collectors → verifier → scorer → synthesizer → presenter |
| Other agents | compare, recommend, grounded chat (JSON and streaming) |
| LLM providers | Groq (`gpt-oss-20b` / `gpt-oss-120b`) or any OpenAI-compatible API, with fallback and per-call metering |
| Coverage | 34 localities · 20 scoring modules · 6 personas |
| API | 43 endpoints under `/api` |
| Quality | 66/66 golden checks · 82 API tests (73 pass locally without LLM or Razorpay keys) |
| Cost | $0.034 average per costed run, measured on an earlier hosted deployment with `gpt-5.4` models; to be re-measured on the current provider ([05](docs/05-cost-model.md)) |

## Documents

| Document | Contents |
|---|---|
| [00 · Design plan](docs/00-design-plan.md) | the original design document, kept as history; parts of it no longer match the code |
| [01 · System architecture](docs/01-system-architecture.md) | local setup, configuration, module map, routes, request and streaming-chat sequences |
| [02 · Agent architecture](docs/02-agent-architecture.md) | the LangGraph topology, node contracts, freshness and search budget, trust gate, scoring, advisor agents, contributions |
| [03 · Data model](docs/03-data-model.md) | collections, ERD, indexes, freshness policy, corpus lifecycle, claim statuses |
| [04 · API reference](docs/04-api-reference.md) | all 43 endpoints, auth, limits, status codes |
| [05 · Cost model](docs/05-cost-model.md) | model tiers, pricing table, LLM routing, calls per action, the run ledger, measured spend |
| [06 · Testing and evals](docs/06-testing-and-evals.md) | golden dataset, the API suite, today's results, known behaviour |
| [07 · Screens](docs/07-screens.md) | every page at desktop and mobile width, light and dark; design system |
| [08 · Call optimizations](docs/08-call-optimizations.md) | every mechanism that saves LLM calls, latency or cost, with file and function |

## Diagrams

Sources are in `diagrams/`. Each diagram in the docs is a verbatim copy of its `.mmd` file.

| File | Type | Used in |
|---|---|---|
| `system-architecture.mmd` | flowchart | 01 |
| `report-sequence.mmd` | sequence | 01 |
| `chat-stream-sequence.mmd` | sequence | 01 |
| `agent-graph.mmd` | flowchart | 02 |
| `data-tiers.mmd` | flowchart | 02 |
| `trust-pipeline.mmd` | flowchart | 02 |
| `advisor-agents.mmd` | flowchart | 02 |
| `contribution-flow.mmd` | flowchart | 02 |
| `data-model.mmd` | ER | 03 |
| `corpus-lifecycle.mmd` | flowchart | 03 |
| `llm-routing.mmd` | flowchart | 05 |
| `cost-ledger.mmd` | flowchart | 05 |

## Folder layout

```
project/
├── README.md                  this file
├── docs/                      00-08
├── diagrams/                  Mermaid sources, one .mmd per diagram
├── reports/                   generated: golden eval run, corpus and cost snapshot
├── screenshots/
│   ├── web/{light,dark}/      1440 × 900, full page
│   └── mobile/{light,dark}/   390 × 844 at 2×, full page
└── scripts/
    ├── capture_screenshots.py regenerate every screenshot
    └── collect_stats.py       regenerate reports/app_stats.json
```

## Regenerating everything

Run from the repo root with MongoDB up, the backend on :8001 and the frontend on :3000.
`backend/.venv` is the backend virtualenv; it also has Playwright for the screenshots.

```bash
backend/.venv/bin/python backend/scripts/run_evals.py           # golden evals -> test_reports/evals_golden_<stamp>.json
cp "$(ls -t test_reports/evals_golden_*.json | head -1)" project/reports/evals_golden_latest.json
(cd backend && .venv/bin/python -m pytest tests -q)            # 82 API tests over HTTP; writes test data
backend/.venv/bin/python project/scripts/collect_stats.py       # overwrites project/reports/app_stats.json
backend/.venv/bin/python project/scripts/capture_screenshots.py # 56 screenshots; see 07 for the landing-page gap

# check that every diagram renders (needs Node and a Chrome that puppeteer can find)
for f in project/diagrams/*.mmd; do npx -y @mermaid-js/mermaid-cli@11 -i "$f" -o "/tmp/$(basename "$f" .mmd).svg"; done
```

## Product rules, as the code enforces them

1. **Absence is a finding.** A module with no inputs gets `score: None`. `rubric.composite()` skips
   it in both numerator and denominator, and the presenter renders an empty card with a
   contribution prompt.
2. **Reported claims need a URL.** The verifier drops `media`, `official` and `forum` facts that
   have no URL, and marks low-confidence any whose host was not among the pages retrieved. Scores
   come from arithmetic, never from a model.
3. **Personas change weights, not facts.** Switching lens re-scores the same cached layers and
   spends no credit. It does run the synthesizer again and refresh layers past their TTL. Only
   the landing page re-weights with no call at all.
4. **Anonymous contributions cannot promote a claim.** They publish as `unverified`, are excluded
   from status reconciliation and from the contributor count that decides whether a claim is
   scored. Once two account holders have made the same claim, anonymous posts do count toward the
   direction it moves the score ([02](docs/02-agent-architecture.md#contribution-pipeline)).
