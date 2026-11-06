# LocalIQ — Project Documentation

**Neighbourhood Quality Reports for Homebuyers · Bengaluru · V1**

Data-driven, persona-weighted, fully-cited quality reports for 34 Bengaluru localities. Every number
on screen traces back to a retrieved source, absence is reported instead of averaged away, and the
cost of producing each report is metered to the token.

| | |
|---|---|
| Stack | FastAPI · MongoDB (Motor) · LangGraph · React 19 · Tailwind · shadcn/ui |
| Agents | 8 nodes: intake → 4 parallel collectors → verifier → scorer → synthesiser → presenter |
| Coverage | 34 Bengaluru localities · 20 scoring modules · 6 personas |
| Trust | 66/66 golden checks · 82 pytest tests · 7 QA passes |
| Cost | $0.034 average per report run (measured over 30 costed runs) |

---

## Contents

| Document | What's inside |
|---|---|
| [01 · System architecture](docs/01-system-architecture.md) | Containers, routing, environment, request lifecycle, caching |
| [02 · Agent architecture](docs/02-agent-architecture.md) | LangGraph topology, every node, the four data tiers, the trust gate |
| [03 · Data model](docs/03-data-model.md) | Collections, ERD, indexes, freshness policy, live corpus stats |
| [04 · API reference](docs/04-api-reference.md) | All 43 endpoints, auth, entitlements, rate limits |
| [05 · Cost model](docs/05-cost-model.md) | Pricing table, per-run ledger design, measured spend |
| [06 · Testing & evals](docs/06-testing-and-evals.md) | Golden dataset, 6 eval suites, pytest suite, all 7 QA passes |
| [07 · Screens](docs/07-screens.md) | Every page, desktop + mobile, light + dark |

## Folder layout

```
project/
├── README.md                  this file
├── docs/                      architecture, API, cost, testing, screens
├── diagrams/                  Mermaid sources (.mmd) for every diagram
├── reports/                   generated: eval run, corpus stats
├── screenshots/
│   ├── web/{light,dark}/      1440×900, full page
│   └── mobile/{light,dark}/   390×844 @2x, full page
└── scripts/
    ├── capture_screenshots.py regenerate every screenshot
    └── collect_stats.py       regenerate reports/app_stats.json
```

## Regenerating everything

```bash
# from the repo root, with the backend venv active and both apps running
(cd backend && python run_evals.py)                      # golden evals -> test_reports/
(cd backend && python -m pytest tests -q)                # 82 backend tests
python project/scripts/collect_stats.py                  # corpus + cost stats
python project/scripts/capture_screenshots.py            # 56 screenshots
```

## Product rules that shaped the architecture

1. **Absence is a finding.** A module with no data renders as an explicit gap with a contribution
   CTA. It is never imputed, and it never enters the weighted average.
2. **Every claim is traceable.** The verifier drops any fact whose source URL was not in the set of
   pages actually retrieved during that run.
3. **Personas change weights, never facts.** Switching lens re-scores the same verified dossier —
   free, instant, no LLM call.
4. **Anonymous contributions are visible but inert.** They publish immediately as `unverified`, and
   are structurally barred from moving a score or corroborating another claim.
