# 04 · API Reference

Base URL: `REACT_APP_BACKEND_URL` + `/api`. Auth is a JWT bearer token from `/api/auth/login`,
stored client-side in `localStorage.lq_token`.

## Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | — | bcrypt hash, returns access token |
| POST | `/api/auth/login` | — | brute-force protected via `login_attempts` |
| POST | `/api/auth/logout` | user | |
| GET | `/api/auth/me` | user | current user + entitlements |
| PUT | `/api/auth/profile` | user | persona + profile answers used by the synthesiser |

## Catalog

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/localities` | user | 34 Bengaluru localities |
| GET | `/api/personas` | user | 6 personas + weights |
| GET | `/api/modules` | user | 20 modules, tier and label |
| GET | `/api/trust/rubric` | user | full rubric + freshness policy (powers /app/trust) |
| GET | `/api/health` | — | liveness |

## Reports

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/reports/generate` | user | entitlement-checked; returns `{job_id}`, runs the graph in the background |
| GET | `/api/reports/job/{job_id}` | user | live agent trace, polled by the Generating screen |
| GET | `/api/reports` | user | list own reports |
| GET | `/api/reports/{id}` | owner | cards, narrative, sources, cost, verifier stats |
| POST | `/api/reports/{id}/lens` | owner | re-score for another persona — **free, no LLM call** |
| POST | `/api/reports/{id}/chat` | owner | grounded Q&A (non-streaming) |
| POST | `/api/reports/{id}/chat/stream` | owner | **SSE** token stream + `###SOURCES` citation block |
| GET | `/api/reports/{id}/chat` | owner | chat history |
| POST | `/api/reports/{id}/share` | owner | mint (once) a public token → `/r/{token}` |
| GET | `/api/public/reports/{token}` | — | public teaser: 3 hero cards, both scores, rest locked |

Chat is capped at **100 messages/day per user**; exceeding it returns `429`.

## Premium

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/compare` | **Pro** | side-by-side, module-by-module delta; `402` for free users |
| POST | `/api/recommend` | user | ranked shortlist; one free run, then Pro |
| GET | `/api/entitlement` | user | reports used / remaining, plan, feature flags |
| GET | `/api/traces` | user | own agent runs with per-run cost + the global ledger |

## Community

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/community/posts` | user | filterable by locality; excludes `removed` |
| POST | `/api/community/posts` | user | PII scrub + toxicity screen; fact claims need proof |
| POST | `/api/community/posts/{id}/vote` | user | ±1, one per user; 5 net upvotes grants a credit |
| POST | `/api/community/proof` | user | base64 image, ≤3 MB |
| GET | `/api/community/proof/{proof_id}` | — | serves the stored image |
| GET | `/api/community/leaderboard` | user | top contributors |
| GET | `/api/community/me` | user | own contributions + credits |

## Contribution links

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/contribute/links` | user | idempotent per (user, locality); embeds the report's current gaps |
| GET | `/api/contribute/links` | user | own links + contribution counts |
| GET | `/api/public/contribute/{token}` | — | locality, inviter, gaps, claim types, recent posts |
| POST | `/api/public/contribute/{token}/proof` | — | anonymous image proof, ≤3 MB |
| POST | `/api/public/contribute/{token}` | — | publishes as `unverified`; **25/day per link, 8/day per IP** |

## Billing (Razorpay, test mode)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/billing/plans` | user | Pro Monthly ₹499 · Pro Annual ₹4,499 |
| POST | `/api/billing/order` | user | creates a Razorpay order |
| POST | `/api/billing/verify` | user | signature verification, upgrades the plan |
| POST | `/api/billing/webhook` | — | HMAC-verified webhook |

## Evals

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/evals/golden` | user | runs all 6 suites live, returns per-check results |
| GET | `/api/evals/dataset` | user | the golden dataset itself: fixtures, frozen values, invariants |

## Status codes used deliberately

| Code | Meaning in LocalIQ |
|---|---|
| `402` | premium feature, free plan — the paywall |
| `403` | authenticated but not the owner of the resource |
| `422` | held by automated moderation (with the reason) |
| `429` | quota: chat 100/day, contribution link 25/day, per-IP 8/day |
