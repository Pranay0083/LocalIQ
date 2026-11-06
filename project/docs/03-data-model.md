# 03 · Data Model

MongoDB 7 in Docker, accessed through Motor. There are 14 collections: 13 are written by the
code, and `traces` only has an index created at startup (nothing writes to it). Routers convert
`_id` to a string `id` before returning a document.

## Entity relationships

<sub>Source: [`diagrams/data-model.mmd`](../diagrams/data-model.mmd)</sub>

```mermaid
erDiagram
    USERS ||--o{ JOBS : starts
    USERS ||--o{ REPORTS : owns
    JOBS |o--o| REPORTS : "report_id"
    REPORTS |o--o{ REPORTS : "lens_of"
    REPORTS ||--o{ CHAT_MESSAGES : "report_id"
    USERS ||--o{ POSTS : "writes when signed in"
    CONTRIB_LINKS ||--o{ POSTS : "link_token, anonymous"
    USERS ||--o{ CONTRIB_LINKS : mints
    POSTS |o--o| PROOFS : "proof_url"
    POSTS ||--o{ VOTES : receives
    USERS ||--o{ VOTES : casts
    USERS ||--o{ ORDERS : pays
    USERS ||--o{ RECOMMENDATIONS : requests
    DOSSIERS ||--o{ REPORTS : "read by run_report"
    DOSSIERS }o--|| CITY_STATS : "percentiles from"

    USERS {
        objectid _id PK
        string email UK
        string password_hash
        string name
        string role "user or admin"
        string plan "free, pro_monthly, pro_annual"
        int reports_used
        int credits
        int recommend_runs
        string persona_key
        object profile
    }
    JOBS {
        string job_id UK
        string user_id FK
        string locality_slug
        string persona_key
        string status "running, done, failed"
        array trace
        object cost
        string report_id
    }
    REPORTS {
        objectid _id PK
        string user_id FK
        string locality_slug
        string persona_key
        string job_id "null for a lens report"
        string lens_of "source report id"
        object composite "score, confidence, coverage"
        object baseline_composite
        object module_scores
        array cards "render blocks + citations"
        object narrative
        array sources
        object layers "ok + collected_at per layer"
        object verifier_stats
        array disputes
        array dropped
        object cost
        string share_token
    }
    DOSSIERS {
        string locality_slug UK
        object domains "air, geo, safety, civic, infra, chatter"
        string updated_at
    }
    CITY_STATS {
        string key UK "bengaluru"
        int localities
        object stats "median, p25, p75, n per module"
        string computed_at
    }
    POSTS {
        objectid _id PK
        string locality_slug
        string kind "fact_claim or experience"
        string claim_type
        string claim_value
        string status "pending, corroborated, verified, unverified"
        bool anonymous
        string user_id "null when anonymous"
        string link_token
        string proof_url
        int upvotes
        int downvotes
        string day
    }
    CONTRIB_LINKS {
        string token UK
        string locality_slug
        string created_by FK
        array gaps
    }
    PROOFS {
        string proof_id UK
        string data "base64 image"
        string mime
        bool anonymous
    }
    VOTES {
        string post_id FK
        string user_id FK
        int value "+1 or -1"
    }
    CHAT_MESSAGES {
        string report_id FK
        string user_id FK
        string role "user or assistant"
        string content
        array used_sources
        string day
    }
    ORDERS {
        string razorpay_order_id
        string user_id FK
        string plan
        int amount "paise"
        string status "created, paid, signature_failed"
    }
    RECOMMENDATIONS {
        string user_id FK
        object persona
        array candidates
        object narrative
        int evaluated
    }
    LOGIN_ATTEMPTS {
        string identifier "ip:email"
        int count
        string last_at
    }
```

## Collections

| Collection | Written by | Purpose and notable fields |
|---|---|---|
| `users` | `routers/auth.py`, `bootstrap.py`, billing, community | account and entitlements: `plan`, `reports_used`, `credits`, `recommend_runs`, `persona_key`, `profile` |
| `jobs` | `routers/reports.py` (`/generate`) | one agent run: `status`, `trace[]`, `cost`, `report_id`, `error` |
| `reports` | `/generate` (via the job), `/lens` | one document per run: `cards[]`, `composite`, `baseline_composite`, `module_scores`, `narrative`, `sources[]`, `layers`, `verifier_stats`, `disputes`, `dropped`, `cost`; `lens_of` on lens reports; `share_token` once shared |
| `dossiers` | `services/cache.save_domain()` | the shared cache: one document per locality, `domains.<layer>` = `{ok, facts, raw, urls, collected_at}` for `air`, `geo`, `safety`, `civic`, `infra`, `chatter` |
| `city_stats` | `services/citystats.compute_city_stats()`, `scripts/seed.py import` | one document, `key: bengaluru`: median, p25, p75 and n per module |
| `posts` | community and contribute routers | fact claims and experiences: `status`, `anonymous`, `link_token`, `proof_url`, `sentiment`, `topics`, `pii_scrubbed`, `credit_granted`, `day` |
| `proofs` | `POST /community/proof`, `POST /public/contribute/{token}/proof` | base64 image (≤ 3 MB decoded) and MIME type |
| `votes` | `POST /community/posts/{id}/vote` | one per user per post, `value` ±1 |
| `contrib_links` | `POST /contribute/links` | `token`, `locality_slug`, `created_by`, `gaps[]` (up to 6) |
| `chat_messages` | both chat endpoints | `role`, `content`, `used_sources`, `missing`, `day` (for the daily cap) |
| `orders` | billing router | Razorpay order id, `plan`, `amount` (paise), `status`: created, paid or signature_failed |
| `recommendations` | `POST /recommend` | the full recommendation result per run |
| `login_attempts` | `security.py` | failed logins per `ip:email`, deleted on success or after the 15-minute lockout |
| `traces` | nothing | index only |

## Indexes

Created on every startup by `db.ensure_indexes()`:

```
users            email                                   unique
login_attempts   identifier
dossiers         locality_slug                           unique
reports          (user_id, created_at desc)
reports          (user_id, locality_slug, persona_key)   the duplicate-report lookup in /generate
jobs             (user_id, created_at desc)
posts            (locality_slug, created_at desc)
posts            (link_token, day)                       per-link daily quota
votes            (post_id, user_id)                      unique: one vote per user per post
chat_messages    (report_id, created_at)
traces           job_id
orders           razorpay_order_id
contrib_links    token                                   unique
contrib_links    (created_by, locality_slug)
```

`jobs.job_id` and `reports.share_token` are queried but not indexed.

## Freshness policy

`rubric.FRESHNESS_POLICY`, evaluated by `services/cache.is_fresh()` against each layer's
`collected_at`.

| Layer | TTL | Source |
|---|---|---|
| `air` | 6 hours | OpenWeather |
| `geo` | 30 days | Overpass / OpenStreetMap |
| `safety` | 7 days | web research |
| `civic` | 14 days | web research |
| `infra` | 60 days | web research |
| `chatter` | 7 days | web research |
| `community` | 0, always live | `posts`, never stored in the dossier |

## Corpus lifecycle

<sub>Source: [`diagrams/corpus-lifecycle.mmd`](../diagrams/corpus-lifecycle.mmd)</sub>

```mermaid
flowchart TB
    subgraph WRITERS["Layer writers, shared by every user"]
        COL["collectors inside a report run<br/>collect_air, collect_geo, collect_web"]
        WARM["scripts/warm.py<br/>geo: air + geo for all 34 localities<br/>web N: research layers for the first N"]
        QD["recommend: _quick_dossier()<br/>air + geo only"]
    end

    COL -->|"save_domain()"| DOS
    WARM -->|"save_domain()"| DOS
    QD -->|"save_domain()"| DOS

    DOS[("dossiers<br/>one document per locality<br/>domains.layer.collected_at")]
    POL["FRESHNESS_POLICY in rubric.py<br/>air 6 h, geo 30 d, safety 7 d,<br/>civic 14 d, infra 60 d, chatter 7 d"]
    POL -.->|"is_fresh() in services/cache.py"| DOS

    SEEDF["backend/seed/corpus.json.gz<br/>dossiers + city_stats only"]
    DOS -->|"scripts/seed.py export"| SEEDF
    SEEDF -->|"scripts/seed.py import, upsert"| DOS

    DOS -->|"compute_city_stats() at startup<br/>and via scripts/warm.py stats"| CS[("city_stats<br/>median, p25, p75 per module")]

    DOS -->|"get_dossier() at intake<br/>fresh layers reused"| RUN["run_report() for one user<br/>verify, score, synthesize, present"]
    CS -->|"get_city_stats(), cached 6 h in process"| RUN
    POSTS[("posts")] -->|"collect_community(), live on every run"| RUN
    RUN --> REP[("reports<br/>one document per run")]

    REP -->|"POST /api/reports/{id}/lens"| LENS["run_report() again for another persona<br/>no credit spent, fresh layers reused<br/>synthesizer called again, stale layers refreshed"]
    LENS --> REP

    SNAP["frontend lens-snapshot.json<br/>3 localities, 6 personas, city medians"] --> LAND["Landing page<br/>composite() re-implemented in the browser<br/>no request, no LLM call"]
```

**Shared, per locality.** A dossier belongs to a locality, not to a user. Any run, from any user,
that refreshes a layer updates it for everyone. Per-user data (reports, chat, posts) never goes
into the dossier.

**Writers.** Three paths write layers, all through `save_domain()`:

- collectors inside a report run (`/generate`, `/lens` or `/compare`) refresh stale layers;
- `scripts/warm.py geo` fetches air and geo for all 34 localities, three at a time, skipping fresh
  layers; `scripts/warm.py web N` fetches the four research layers for the first `N` localities in
  `localities.py` order, skipping fresh layers and stopping everything on a Groq rate limit (it
  does not apply `SEARCH_BUDGET_PER_DOSSIER`); `scripts/warm.py stats` recomputes `city_stats`;
- `recommend` refreshes stale air and geo layers for its candidates.

**Seed file.** `scripts/seed.py export` writes `dossiers` and `city_stats` (nothing else) to
`backend/seed/corpus.json.gz`; `import` upserts them by `locality_slug` and `key` and never
deletes. The committed file holds 34 dossiers with a `geo` layer each and one `city_stats`
document. Imported layers keep their original `collected_at` (2026-11-06 for these), so they count
as fresh until the 30-day geo TTL runs out. There are no air or research layers in the file; on a
fresh install those are collected on first use or by `warm.py`.

**City percentiles.** `compute_city_stats()` re-verifies and re-scores every dossier that has a geo
layer, then stores median, p25 and p75 per module (modules with fewer than 3 scores are skipped).
It runs at startup when at least 3 such dossiers exist, and on `warm.py stats`. The presenter reads
it through `get_city_stats()`, which caches it in process for 6 hours, and `percentile_of()` adds
`city_median`, `delta` and a quartile label to each card. The score ledger draws the median as a
tick.

**Lens switching.** `POST /api/reports/{id}/lens` calls `run_report()` again with the new persona
and `force=False`, and stores the result as a new report with `lens_of` set. It spends no credit
and reuses every fresh layer, but it is a full graph run: the synthesizer is called again (one
smart-tier call), and any layer past its TTL is refreshed first. In practice the air layer (6 h)
is often stale. The landing page is different: it re-weights the fixed scores in
`lens-snapshot.json` in the browser, with the same formula as `rubric.composite()`, and makes no
request.

## Claim status ladder

`posts.status`, set by `_reconcile_claim_status()` each time an account holder posts a fact claim.
It counts non-anonymous, non-removed fact claims of the same `claim_type` in the same locality.

| Status | Condition |
|---|---|
| `pending` | default for an account holder's post |
| `corroborated` | 2 or more distinct account holders and 2 or more of their posts carry proof; every post in the group earns its author 1 credit, once |
| `verified` | 3 or more distinct account holders and 3 or more posts with proof |
| `unverified` | every anonymous post from a contribution link; never changed by reconciliation |
| `removed` | excluded from every query; no endpoint sets it, so it is set by hand in the database |

A post also earns its author 1 credit when its net votes reach +5. A credit pays for one report.

Whether a claim moves a score is decided separately, at run time, by `collect_community()`; see
[02 · Contribution pipeline](02-agent-architecture.md#contribution-pipeline).

## Corpus snapshot from the earlier hosted deployment

`project/reports/app_stats.json` was generated on 2026-09-03 against the database of an earlier
hosted deployment, not the local one. Regenerating it with
`backend/.venv/bin/python project/scripts/collect_stats.py` overwrites it with counts from
whatever database `backend/.env` points at.

| Entity | Count in the snapshot |
|---|---|
| Users | 126 |
| Reports | 64 |
| Agent runs (jobs) | 33 |
| Dossiers | 34 |
| Community posts | 112: 27 verified, 77 pending, 8 anonymous unverified |
| Photo proofs | 31 |
| Votes | 48 |
| Chat messages | 275 |
| Orders (test mode) | 50 |
| Contribution links | 1 |
