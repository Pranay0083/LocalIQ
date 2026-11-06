# 08 · Call Optimizations

Every mechanism in the code that reduces LLM calls, paid searches, latency or spend, with the file
and function that implements it. Paths are relative to `backend/app/` unless they start with
`frontend/`. The last section lists what the code does not do, so none of this is read as more
than it is.

## 1 · Calls that are never made

| # | Mechanism | Where | Effect |
|---|---|---|---|
| 1.1 | **Duplicate report short-circuit.** A `/generate` for a (user, locality, persona) that already has a report returns it with `cached: true` | `routers/reports.py`, `generate()` | no job, no graph run, no credit, 0 LLM calls. `force: true` bypasses it |
| 1.2 | **Shared per-locality dossier.** Layers are stored per locality, not per user, and reused by every user's run | `services/cache.py`, `get_dossier()` and `save_domain()`; `agents/graph.py`, `node_intake()` seeds cached layers into state | the second user to ask about a locality pays for no research |
| 1.3 | **Per-layer freshness.** Each layer has its own TTL; only stale layers are refreshed | `rubric.py`, `FRESHNESS_POLICY`; `services/cache.py`, `is_fresh()` and `stale_domains()`; `agents/graph.py`, `_skip()` in each collector node | research layers stay valid for 7 to 60 days, so most runs are warm. A warm run makes 1 LLM call |
| 1.4 | **Deterministic trust gate and scoring.** Verification, the 20 module scores, the persona composite and the baseline are arithmetic | `agents/verifier.py`, `verify()`; `agents/scorer.py`, `score_all()`; `rubric.py`, `composite()` | no LLM call is spent on scoring, ever |
| 1.5 | **One prose call per report.** The synthesizer is the only writer; its one JSON reply also carries the one-line text for every module card. Cards, render blocks and citations are built in code | `agents/graph.py`, `node_synthesize()`; `agents/presenter.py`, `present()` and `build_renders()` | 1 smart-tier call per report instead of one per card |
| 1.6 | **Recommendation scored without an LLM.** 10 candidates are scored from the free air and geo layers; only the final narrative uses a model | `agents/advisor.py`, `_quick_dossier()` and `recommend()` | 1 LLM call for 10 localities, no research |
| 1.7 | **Chat suggestions built in the browser** from the report's own cards | `frontend/src/components/report/ChatPanel.jsx`, `buildSuggestions()` | 0 calls |
| 1.8 | **Landing-page lens in the browser.** Re-weights a fixed snapshot with the same formula as `rubric.composite()` | `frontend/src/pages/landing/Landing.jsx`, `composite()`; `lens-snapshot.json` | 0 requests, 0 calls |
| 1.9 | **Golden evals without an LLM.** All 66 checks are arithmetic and contract checks | `evals/runner.py`, `run_golden()` | the eval suite costs nothing to run |
| 1.10 | **Corpus prepared ahead of time.** `warm.py` fills layers offline; `seed.py import` loads the committed geo layers and city stats | `scripts/warm.py`, `warm_free()` and `warm_web()`; `scripts/seed.py`, `import_corpus()` | imported layers keep their original `collected_at` (2026-11-06 for the committed geo layers), so a fresh install needs no Overpass call until those layers pass the 30-day geo TTL |
| 1.11 | **City percentiles computed once.** Stored in `city_stats` and cached in process | `services/citystats.py`, `compute_city_stats()` and `get_city_stats()` (6-hour cache) | presenters do not re-score 34 localities per report |

**Lens switching, precisely.** `POST /api/reports/{id}/lens` (`routers/reports.py`,
`switch_lens()`) spends no credit and reuses every fresh layer through 1.2 and 1.3. It is still a
full `run_report()`: the synthesizer is called again, and any layer past its TTL is refreshed
first. Only the landing page (1.8) re-scores with no call.

## 2 · Calls that are bounded

| # | Mechanism | Where | Effect |
|---|---|---|---|
| 2.1 | **Search budget per run.** Only the first `SEARCH_BUDGET_PER_DOSSIER` stale research layers are collected, one at a time | `agents/graph.py`, `node_web()` | caps research calls per run (template value 4 = all four layers); sequential calls stay under rate limits |
| 2.2 | **Key-free retrieval instead of paid search.** Google News RSS, publisher pages, Wikipedia and Reddit are fetched over HTTP; the model only plans queries and extracts | `services/research.py`, `local_research()`; routed by `services/llm/__init__.py`, `web_research()` | no per-search fee; 2 token-metered calls per layer. Used with `RESEARCH_PROVIDER=local`, with `auto` and no `GROQ_API_KEY`, or as the fallback when Groq search fails |
| 2.3 | **Corpus size caps.** At most 10 documents of 3,800 characters reach the extraction prompt; query planning is capped at 500 output tokens | `services/research.py`, `MAX_DOCS`, `DOC_CHARS`, `_gather()`, `_plan()` | bounds the largest prompt in the system |
| 2.4 | **Prompt truncation.** Profile 900 characters and disputes 600 in the synthesizer; chat context 70 cited facts, narrative 1,200 characters, last 6 turns of 300 characters; research notes 6,000 characters in the JSON repair call; posts 1,200 characters in moderation | `agents/graph.py`, `node_synthesize()`; `agents/advisor.py`, `_chat_context()`; `agents/collectors.py`, `_research_json()`; `routers/community.py`, `screen_post()` | bounded input tokens per call |
| 2.5 | **Fast and smart tiers.** Only the synthesizer, compare verdict and recommend narrative use the smart model | `config.py`, `model_fast` / `model_smart`; callers in `agents/graph.py` and `agents/advisor.py` | chat, moderation and research run on the cheaper model |
| 2.6 | **`reasoning_effort="low"`** on Groq gpt-oss models | `services/llm/groq_provider.py`, `chat()` and `web_search()` (not `stream()`) | fewer reasoning tokens billed as output |
| 2.7 | **Usage caps.** Chat 100 user turns per day; 10 posts per user per day; 25 anonymous posts per link per day, 8 per IP when `X-Forwarded-For` is present; `FREE_REPORT_LIMIT`; compare for Pro only; one free recommendation | `routers/reports.py`, `report_chat()`, `report_chat_stream()`, `entitlement()`; `routers/community.py`, `create_post()`; `routers/contribute.py`, `_guard_quota()` | bounds spend per account and per link |
| 2.8 | **Stop on a rate limit.** A Groq 429 on search returns `rate_limited` without retrying; the run keeps the cached layer; `warm.py web` stops all remaining work | `services/llm/groq_provider.py`, `web_search()`; `agents/graph.py`, `node_web()`; `scripts/warm.py`, `warm_web()` | no retry storm against an exhausted quota |

## 3 · Latency

| # | Mechanism | Where | Effect |
|---|---|---|---|
| 3.1 | **Parallel collectors.** Air, geo, web and community start in the same graph step | `agents/graph.py`, `build_graph()` | a run takes as long as its slowest collector, not the sum |
| 3.2 | **Concurrent fetching in research.** All article, Wikipedia and Reddit fetches run with `asyncio.gather`, at most 10 at a time | `services/research.py`, `_gather()`, `_fetch_gate` | documents are fetched side by side instead of one after another (each news item still needs its own sequential decode and fetch) |
| 3.3 | **One Overpass query per locality** covering every amenity category, roads, rail and bus stops | `services/geo.py`, `QUERY`, `fetch_geo()` | one request instead of one per category |
| 3.4 | **Bounded concurrency in recommend.** Candidate dossiers are built 3 at a time | `agents/advisor.py`, `recommend()` | faster than one at a time without flooding Overpass |
| 3.5 | **Job in the background.** `/generate` returns a `job_id` at once and the UI polls the trace | `routers/reports.py`, `generate()`, `_execute_job()` | the request never waits for the run |
| 3.6 | **Streamed chat.** Tokens are sent as they arrive | `agents/advisor.py`, `stream_answer()`; `routers/reports.py`, `report_chat_stream()` | first words appear before the answer is complete |

## 4 · Retries and failure handling

| # | Mechanism | Where | Effect |
|---|---|---|---|
| 4.1 | **No retry on 413.** Groq returns 413 when one request is larger than the tier's tokens-per-minute; waiting cannot fix that, so the call goes straight to the fallback provider | `services/llm/groq_provider.py`, `chat()` | no wasted attempts and no backoff delay on oversized research prompts |
| 4.2 | **Backoff on 429 and 503.** Up to 3 attempts, sleeping 1.5 s × 2^attempt; network errors sleep 1.5 s | `services/llm/groq_provider.py`, `chat()` | rides out short rate-limit windows |
| 4.3 | **Empty reply, bigger budget.** A reasoning model that spends the whole budget thinking gets `max_tokens` doubled on the next attempt | `services/llm/groq_provider.py`, `chat()` | turns a failed step into one extra call |
| 4.4 | **Provider fallback at the same tier.** A failed Groq chat retries once on the OpenAI-compatible provider, mapping the fast or smart id to `OPENAI_MODEL_FAST` or `OPENAI_MODEL_SMART` | `services/llm/__init__.py`, `chat()`; `services/llm/compat_provider.py`, `model_for()` | a narrative still gets written on the intended tier |
| 4.5 | **SDK retries on the compatible provider.** `AsyncOpenAI(max_retries=4)` uses the SDK's exponential backoff | `services/llm/compat_provider.py`, `_client` | absorbs free-tier 429s |
| 4.6 | **Overpass mirrors.** Every mirror in `OVERPASS_URL`, two passes, 3 s apart | `services/geo.py`, `_overpass()` | one flaky public instance does not fail the geo layer |
| 4.7 | **Fixed fallbacks instead of app-level retries.** Synthesizer, compare, recommend and chat return a template or apology when no JSON arrives; a failed collector keeps the cached layer | `agents/graph.py`, `node_synthesize()`, `node_intake()`; `agents/advisor.py` | a failure costs at most the attempts above, never a loop |

## 5 · Metering

| # | Mechanism | Where | Effect |
|---|---|---|---|
| 5.1 | **Per-run ledger.** A `ContextVar` dict per `run_report()` | `services/llm/ledger.py`, `new_run_ledger()`, `record()`; `agents/graph.py`, `run_report()` | each report shows its own cost, even with concurrent runs |
| 5.2 | **$0 for local models.** Any `OPENAI_BASE_URL` on `localhost` or `127.0.0.1` is recorded at zero cost | `services/llm/compat_provider.py`, `IS_LOCAL`; `ledger.record(free=True)` | Ollama or LM Studio runs are not billed at a cloud rate |
| 5.3 | **Default rate for unknown models.** Unlisted model ids are priced at `DEFAULT_RATE` (0.15 / 0.60) | `services/llm/ledger.py` | a new model id never shows up as free |

## What the code does not do

- There is no prompt caching, response caching or semantic cache. The same chat question asked
  twice is answered twice.
- `/lens` is not free of LLM calls: it reruns the synthesizer and refreshes stale layers.
- `/compare` runs the full graph for each locality, including a synthesizer call whose narrative it
  uses only for the headline.
- Streaming chat has no retry and no provider fallback.
- No tokens are counted before a request is sent; an oversized request is discovered by Groq's 413.
- `scripts/warm.py web` does not apply `SEARCH_BUDGET_PER_DOSSIER`.
- Moderation fails open: when no model answers, `screen_post()` treats the post as not toxic.
