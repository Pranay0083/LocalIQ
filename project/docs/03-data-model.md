# 03 · Data Model

MongoDB, 14 collections, accessed through Motor. Documents are written by explicit field, never by
spreading a raw Mongo doc into a response — `_id` is always converted to a string `id` at the API
boundary.

## Entity relationships

```mermaid
erDiagram
    USERS ||--o{ REPORTS : owns
    USERS ||--o{ JOBS : triggers
    USERS ||--o{ POSTS : writes
    USERS ||--o{ VOTES : casts
    USERS ||--o{ ORDERS : pays
    USERS ||--o{ CONTRIB_LINKS : mints
    USERS ||--o{ RECOMMENDATIONS : requests
    JOBS ||--|| REPORTS : produces
    REPORTS ||--o{ CHAT_MESSAGES : "grounds"
    DOSSIERS ||--o{ REPORTS : "cached input for"
    CONTRIB_LINKS ||--o{ POSTS : "collects (anonymous)"
    POSTS ||--o| PROOFS : "backed by"
    POSTS ||--o{ VOTES : "receives"
    LOCALITIES ||--o{ DOSSIERS : "1 per locality"
    LOCALITIES ||--o{ POSTS : "scoped to"

    USERS { string email PK "unique" string password_hash string plan "free|pro" string persona_key object profile int reports_used int credits string role }
    REPORTS { objectid _id string user_id string locality_slug string persona_key float composite float baseline_composite array cards array sources object narrative object cost object verifier_stats string share_token }
    JOBS { string job_id PK string status "queued|running|done|failed" array trace object cost string report_id }
    DOSSIERS { string locality_slug PK object domains "air|geo|safety|civic|infra|chatter" string updated_at }
    POSTS { objectid _id string locality_slug string kind "fact_claim|experience" string claim_type string status bool anonymous string link_token string proof_url int upvotes int downvotes }
    CONTRIB_LINKS { string token PK string locality_slug string created_by array gaps }
    PROOFS { string proof_id PK string data "base64" string mime }
    ORDERS { string razorpay_order_id PK int amount string plan string status }
    CHAT_MESSAGES { string report_id string role "user|assistant" string content string day }
    VOTES { string post_id string user_id int value }
    RECOMMENDATIONS { string user_id array candidates object narrative }
    CITY_STATS { string key PK object stats array localities }
```

## Collections

| Collection | Purpose | Notable fields |
|---|---|---|
| `users` | accounts + entitlements | `plan`, `reports_used`, `credits`, `persona_key`, `profile` |
| `reports` | finished reports | `cards[]`, `sources[]`, `narrative`, `cost`, `verifier_stats`, `share_token` |
| `jobs` | one agent run | `trace[]` (streamed to the UI), `cost`, `status` |
| `dossiers` | **the cache** — one doc per locality, one sub-doc per layer | `domains.{air,geo,safety,civic,infra,chatter}` each with `collected_at` |
| `posts` | community claims + experiences | `status`, `anonymous`, `link_token`, `proof_url`, `pii_scrubbed` |
| `contrib_links` | shareable contribution links | `token`, `gaps[]`, `created_by` |
| `proofs` | base64 photo proof | `proof_id`, `mime` |
| `votes` | one vote per user per post | `value` ±1 |
| `chat_messages` | grounded chat history | `day` (used for the 100/day cap) |
| `orders` | Razorpay orders (test mode) | `razorpay_order_id`, `status` |
| `recommendations` | recommendation runs | `candidates[]`, `evaluated` |
| `city_stats` | city-wide medians for the "vs city" comparisons | `stats` |
| `login_attempts` | brute-force protection | — |
| `traces` | reserved for long-term trace retention | — |

## Indexes (created at startup in `db.py`)

```
users.email                      unique
reports.(user_id, created_at)    compound, descending
reports.share_token
jobs.job_id                      unique
dossiers.locality_slug           unique
posts.(locality_slug, created_at)
posts.(link_token, day)          quota lookups
votes.(post_id, user_id)         unique — one vote per user per post
orders.razorpay_order_id
contrib_links.token              unique
contrib_links.(created_by, locality_slug)
```

## Freshness policy

Cached per layer, evaluated by `services/cache.py` on every run.

| Layer | TTL | Rationale |
|---|---|---|
| `air` | 6 hours | AQI moves within a day |
| `geo` | 30 days | OSM amenity mesh barely moves |
| `safety` | 7 days | news-driven |
| `civic` | 14 days | water/power reporting is episodic |
| `infra` | 60 days | metro/road projects move in quarters |
| `chatter` | 7 days | forum sentiment |
| `community` | always live | residents post continuously |

## Claim status ladder

| Status | How it is reached | Enters the score? |
|---|---|---|
| `unverified` | anonymous contribution via a shared link | **no** |
| `pending` | one account holder, with proof | no |
| `corroborated` | a second account holder agrees | partially, lower confidence |
| `verified` | 2+ account holders **and** photo proof | yes |
| `disputed` | contradicting claims | no — both sides rendered |
| `removed` | moderation | no |

`_reconcile_claim_status` explicitly excludes `anonymous: true` documents, and
`collectors.collect_community` excludes them from the contributor set — so no volume of anonymous
posts can promote a claim.

## Live corpus (see `reports/app_stats.json` for the generated snapshot)

| Entity | Count |
|---|---|
| Users | 126 |
| Reports | 64 |
| Agent runs (jobs) | 33 |
| Cached dossiers | 34 (full Bengaluru coverage) |
| Community posts | 112 — 27 verified · 77 pending · 8 anonymous unverified |
| Photo proofs | 31 |
| Votes | 48 |
| Chat messages | 275 |
| Orders (test mode) | 50 |
| Contribution links | 1 |
