# 04 · API Reference

43 endpoints, all under `/api`. Base URL: `REACT_APP_BACKEND_URL` (locally
`http://localhost:8001`). FastAPI also serves the generated schema at `/openapi.json` and Swagger
UI at `/docs`.

**Auth column.** `—` no auth. `user` needs a valid JWT (Bearer header or `access_token` cookie).
`owner` additionally requires that the caller owns the resource; a report or job that belongs to
someone else returns `404`, not `403`, so ids cannot be probed.

| Router | File | Endpoints |
|---|---|---|
| App | `app/main.py` | 2 |
| Auth | `routers/auth.py` | 5 |
| Catalog, reports, advisors, account | `routers/reports.py` | 16 |
| Share | `routers/share.py` | 2 |
| Community | `routers/community.py` | 7 |
| Contribute | `routers/contribute.py` | 5 |
| Billing | `routers/billing.py` | 4 |
| Evals | `routers/evals.py` | 2 |
| **Total** | | **43** |

## App

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/` | — | service name and status |
| GET | `/api/health` | — | pings MongoDB |

## Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | — | `{email, password (6-128), name}`; `409` if the email exists; returns the user and `access_token`, sets cookies |
| POST | `/api/auth/login` | — | `401` on bad credentials; `429` after 5 failures for the same `ip:email`, for 15 minutes |
| POST | `/api/auth/logout` | — | clears the auth cookies |
| GET | `/api/auth/me` | user | current user |
| PUT | `/api/auth/profile` | user | profile answers (`stage`, `household`, `work_locality`, `work_mode`, `budget_band`, `commute_tolerance`, `free_text`) and `persona_key` |

## Catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/localities` | — | `?q=&limit=40`; each locality has `warm: true` when a dossier exists |
| GET | `/api/personas` | — | 6 personas with weights and the modules each selects |
| GET | `/api/modules` | — | 20 modules: key, label, icon, tier |
| GET | `/api/trust/rubric` | — | formula text per module, personas, baseline weights, freshness policy, source types, principles |

## Reports

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/reports/generate` | user | `{locality, persona_key?, overrides?, force}`. `locality` may be a slug, name or pincode. Returns `{job_id, report_id, cached}`. An existing report for the same user, locality and persona is returned with `cached: true` and no charge unless `force`. `404` outside Bengaluru, `400` unknown persona, `402` when no free report or credit is left |
| GET | `/api/reports/job/{job_id}` | owner | job status and `trace[]`, polled by the Generating screen |
| GET | `/api/reports` | user | own reports, newest per (locality, persona), up to 40, without cards |
| GET | `/api/reports/{id}` | owner | the full report document |
| POST | `/api/reports/{id}/lens` | owner | `{persona_key, overrides?}`. Re-runs the graph on the cached dossier and stores a new report. No credit; one synthesizer call; stale layers are refreshed |
| POST | `/api/reports/{id}/chat` | owner | `{message}` (1-1000 chars); JSON answer with `used_sources` and `missing` |
| POST | `/api/reports/{id}/chat/stream` | owner | same input; `text/event-stream` with `delta`, `done` and `error` frames |
| GET | `/api/reports/{id}/chat` | user | the caller's last 80 turns on that report, oldest first |

Both chat endpoints count the user's turns across all reports and return `429` at 100 per UTC day.

## Advisors and account

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/compare` | user, Pro | `{slugs: 2-3, persona_key?}`; `402` for free plans. Runs `run_report()` per locality, then one comparison call. Not stored |
| POST | `/api/recommend` | user | ranked shortlist of 5 from 10 candidates; free plans get one run, then `402`. Stored in `recommendations` |
| GET | `/api/entitlement` | user | plan, reports used, free left, credits, `can_generate`, `can_compare`, `can_recommend` |
| GET | `/api/traces` | user | own last 20 jobs with cost, plus the process-wide token ledger |

## Share

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/reports/{id}/share` | owner | mints a token once and returns `{token, path: /r/{token}}` |
| GET | `/api/public/reports/{token}` | — | teaser: both scores, part of the narrative, the first 3 cards that have data, the rest listed as locked |

## Community

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/community/posts` | — | `?locality_slug=&kind=&limit=50`; excludes `removed` |
| POST | `/api/community/posts` | user | PII scrub, LLM moderation (`422` if held), fact claims need a valid `claim_type` and `proof_id`; 10 posts per user per day (`429`) |
| POST | `/api/community/posts/{id}/vote` | user | `{value: 1 or -1}`; `409` for a repeated vote; a post that reaches net +5 earns its author a credit |
| POST | `/api/community/proof` | user | `{data_url}` image, `413` above 3 MB |
| GET | `/api/community/proof/{proof_id}` | — | serves the stored image |
| GET | `/api/community/leaderboard` | — | top contributors by corroborated or verified posts, then upvotes |
| GET | `/api/community/me` | user | own posts, totals, credits earned, posting streak |

## Contribution links

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/contribute/links` | user | `{locality_slug, report_id?}`; one link per user and locality; copies up to 6 gaps from the report's empty cards |
| GET | `/api/contribute/links` | user | own links with contribution counts |
| GET | `/api/public/contribute/{token}` | — | locality, inviter name, gaps, claim types, 5 recent posts |
| POST | `/api/public/contribute/{token}/proof` | — | anonymous image proof, `413` above 3 MB |
| POST | `/api/public/contribute/{token}` | — | publishes with `anonymous: true`, `status: unverified`. `429` after 25 posts per link per day, or 8 per IP per day when an `X-Forwarded-For` header is present (without a proxy that sets it, only the per-link cap applies) |

## Billing (Razorpay test mode)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/billing/plans` | user | Free, Pro Monthly ₹499, Pro Annual ₹4,499, the current plan and the Razorpay key id |
| POST | `/api/billing/order` | user | creates a Razorpay order; `502` if the gateway call fails |
| POST | `/api/billing/verify` | user | HMAC-SHA256 signature check, then sets the plan; `400` on a bad signature |
| POST | `/api/billing/webhook` | — | verifies `X-Razorpay-Signature`; `payment.captured` sets the plan |

## Evals

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/evals/golden` | user | runs all 6 suites (66 checks) and returns per-check results |
| GET | `/api/evals/dataset` | user | dataset version, fixtures, frozen expectations, invariants, persona modules, block contract |

## Status codes used on purpose

| Code | Meaning in LocalIQ |
|---|---|
| `400` | bad id, unknown persona or plan, missing proof, bad payment signature |
| `401` | missing, expired or invalid token |
| `402` | paywall: no free report or credit left, compare on a free plan, second free recommendation |
| `404` | not found, or not yours; a locality outside Bengaluru |
| `409` | email already registered, repeated vote |
| `413` | proof image above 3 MB |
| `422` | post held by automated moderation (with the reason), or request validation |
| `429` | login lockout, chat 100/day, posts 10/day, link 25/day, IP 8/day |
| `502` | Razorpay order creation failed |
