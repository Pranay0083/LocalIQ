# Neighborhood Quality Reports — Build Plan (v2)

A "credit score for neighborhoods." Pick a locality in Bangalore and get a standardized, cited,
**persona-shaped** report — assembled live by a multi-agent system, not a static page. Then ask
follow-up questions in chat, compare shortlisted localities, get recommendations based on your own
situation, and contribute what you know back to the community.

Changes from v1, per feedback: Bangalore only · report sections adapt to who the user is · Google
Maps replaced by agentic web search + open geodata · crime built from news/web signals · community
contribution live from day one · Razorpay test mode for the paywall.

---

## 1. Decisions locked

| Decision | Choice |
|---|---|
| LLM + orchestration | Groq, LangGraph multi-agent |
| City at launch | **Bangalore only.** More cities after V1 proves out. |
| Login | Email + password |
| Payments | **Razorpay test mode.** 5 free reports, then a real (test-mode) checkout. |
| Report format | In-app, chat-first. No PDFs. |
| Report shape | **Adaptive per persona** — not a fixed set of sections |
| Primary user | Active buyer/renter comparing 2–3 shortlisted localities |
| External sources | Used and **shown with a source tag** when the user asks where a claim came from |
| Community | Live from day one — experience posts + proof-backed fact claims |
| V1 scope | Report, chat, comparison, profile recommender, community |

---

## 2. The report adapts to the person — this is now the core mechanic

A single fixed report is what every existing portal already does badly. A bachelor does not care
about CBSE school rankings; they care about cafés open past 11pm, gym density, how late it stays
safe to walk, and rent. A family with a five-year-old cares about the opposite. The report is
assembled from a **catalogue of modules**, and the agent picks which ones run.

**Module catalogue** (each is independently scored, sourced and dated):

Air quality · Commute & connectivity · Safety (day) · Safety (late night) · Nightlife & cafés ·
Restaurants & food · Schools & childcare · Parks & green cover · Healthcare access · Daily needs
(groceries, markets, ATMs) · Fitness & sports · Places of worship · Water reliability · Power
reliability · Noise & construction · Internet & work-from-home suitability · Pet friendliness ·
Rent & cost band · Future infrastructure · Investment signals

**How the agent decides which modules run:**

1. **Profile** — stage (buyer / renter / investor / student), household, work location, work mode,
   budget, and free-text ("I'm a bachelor, I code, I like live music and I have a dog").
2. **Persona inference** — the agent maps that to a weighted module set. Six starting presets
   (Bachelor/young professional · Student · Family with kids · Living with elderly parents ·
   WFH professional · Investor), each with different modules and different weights.
3. **Clarifying questions** — if the profile is thin, the agent asks 2–3 targeted questions before
   generating rather than guessing. It explains why it is asking.
4. **Manual override** — the user can add or drop any module and pin the ones that matter most.
   The report re-renders without a full regeneration.

**Consequence that must be visible in the UI:** the composite score becomes **persona-weighted**.
Whitefield can score 78 for an investor and 54 for a bachelor, and both are correct. The report
always shows "scored for: WFH professional with a dog" alongside the number, and lets the user
switch lens to see how it changes. Without that label the score is misleading; with it, it is the
single most differentiated thing in the product.

---

## 3. Where the data actually comes from

Three tiers, each used for what it is genuinely good at. Nothing is invented.

### Tier 1 — Live API (exact, real-time)
**OpenWeather Air Pollution** (key provided). Live PM2.5/PM10/NO₂/SO₂/O₃/CO per locality
coordinate, plus forecast and historical trend. Converted to Indian CPCB AQI bands, not the raw
1–5 index. This is genuinely micro-zone and genuinely real-time.

### Tier 2 — Open geodata (exact, free, no key)
**OpenStreetMap / Overpass.** Handles every "nearest X and how far" question **deterministically**:
nearest metro station and walking distance, nearest police station, hospitals within 3 km, café and
pub counts, school inventory, park area, gym density, ATM coverage, distance from a stated work
address. Free, no key, and — critically — **computed geometry rather than a language model guessing
a number**. Distances in this product are never produced by an LLM.

### Tier 3 — Agentic web search (recency, reputation, narrative)
This replaces the missing Google Maps key. **Groq's built-in web search and page-visit tooling runs
on the same Groq key already provided** — no new account, no new key, no scraping infrastructure.
The agent issues targeted queries and gets back content **with citations**, which is exactly the
"just query it smartly" behaviour requested.

What Tier 3 covers:
- **Crime & safety** — targeted searches for incidents reported in and around a locality over a
  rolling window, plus police-jurisdiction context and any published district statistics.
- **Future infrastructure** — metro line extensions and station timelines, road and flyover
  projects, sewage and water-supply upgrades, from authority announcements and press coverage.
- **Place reputation** — how specific cafés, markets, hospitals and schools are talked about, since
  Google review text is unavailable.
- **Water and power reliability** — reported outage patterns, scheduled cuts, tanker dependence.
- **Resident chatter** — Reddit, forums and local coverage, always tagged as unverified.

**Costs are real but small:** Groq bills built-in search separately from tokens (roughly $5–8 per
1,000 searches, $1 per 1,000 page visits). A full locality dossier runs on the order of 15–25
searches and 8–12 page visits — a few cents. Warming all of Bangalore is a few dollars, once.

### The crime layer, restated honestly
The v1 plan said crime would underdeliver. The web-search approach is better, but its output is a
**different thing** and must be labelled as such:

> "12 incidents reported in local media in the last 12 months within ~2 km, mostly chain-snatching
> and two-wheeler theft, concentrated near [area]. Media-reported incidents are not official crime
> statistics and under-represent unreported crime."

Recency-weighted, category-broken-out, every incident linked to its source article with a date. Plus
official district figures where they exist, plus community reports. Never a bare "safe/unsafe" badge.
This is more useful and more current than annual NCRB tables, and it is not the same as a crime rate.

---

## 4. The agent system

Seven roles in a LangGraph graph, with expensive work cached per locality and cheap work
personalized per user.

**The design constraint that shapes everything:** facts about Koramangala 4th Block do not change
per user — only the interpretation does. So heavy multi-source collection runs **once per locality**
and is cached with per-source freshness timestamps. Each user's report is a thin personalization
pass over that shared dossier. This is what keeps cost and Groq rate limits survivable (§9), and it
makes "regenerate" mean something real instead of burning money to produce the same page.

1. **Intake / Router** — resolves free text ("Koramangala 4th block", a pin code, "near my office in
   Whitefield") to a known locality, infers the persona and module set (§2), asks clarifying
   questions if needed, and decides whether the cached dossier is fresh enough.
2. **Collector agents, fanned out in parallel** — one per domain, each with a strict tool allow-list.
   Air, Geo/Amenities, Safety & News, Civic (water/power), Education, Infrastructure, Reputation &
   Chatter, Community. Each returns typed, cited facts or an explicit "no data found." Never prose,
   never an unsourced number.
3. **Verifier** — the trust gate. Cross-checks every claim against the raw retrieved payload, drops
   anything untraceable, resolves or flags contradictions (community says daily 6-hour cuts, utility
   notice says none), assigns per-field confidence, and marks anything only a human should judge.
4. **Scorer** — converts verified facts into 0–100 module scores using a **fixed, published,
   deterministic rubric**, then applies the persona weights. Not an LLM judgment call. Missing data
   widens a confidence band; it never quietly becomes an average.
5. **Synthesizer** — the "what living here actually looks like *for you*" narrative. Can only
   reference facts the Verifier passed.
6. **Comparator** — for 2–3 localities: where each wins, where each loses, the real trade-off given
   the user's stated priorities, and a recommendation with reasoning.
7. **Presenter** — emits the strict JSON contract the UI renders: which chart for which metric,
   which cards in which order, which badges, which citation attaches to which number. The frontend
   has zero layout intelligence — the agent decides the shape of the page. New module types appear
   without frontend work.

Plus a **Chat agent** that answers follow-ups against the cached dossier (cheap, grounded, no
re-collection), and escalates to a single targeted collector refresh only when the question needs
data the dossier genuinely lacks.

**Memory and reuse** — everything retrieved is stored with its source, fetch time, and a freshness
policy: air quality expires in hours, amenities in weeks, news in days, infrastructure in months.
Regeneration refreshes only what is actually stale, and shows the user what changed since last time.

**Human in the loop** — a community fact claim contradicting an official source goes to moderation
rather than silently overriding it; Verifier-flagged conflicts surface in the report as a visible
"disputed" marker rather than being guessed away.

---

## 5. What the user sees

- **Onboarding profile** — skippable but high-leverage. Stage, budget band, work location, household,
  commute tolerance, work mode, and a free-text "tell me about yourself."
- **Home** — locality search, recent reports, saved localities, a Bangalore map view.
- **Report** — persona-labelled composite score, module cards in agent-decided order, AQI trend
  chart, amenity/distance panel, crime-incident timeline with sources, infrastructure timeline,
  "what this means for you" narrative, disputed markers, freshness badges, and a citation drawer on
  every single number.
- **Lens switcher** — re-score the same locality as a different persona, instantly.
- **Chat** — ask anything about this locality; answers cite the same sources.
- **Compare** — 2–3 localities side by side with a verdict and reasoning. **Premium.**
- **Recommend** — "given my profile, where should I look?" → ranked 3–5 with reasoning.
- **Community** — per-locality feed, contribution prompt on every report.
- **Account** — report counter, plan, Razorpay checkout.

---

## 6. Trust model

The only real moat, so it is a feature and not a footnote:

- Every number has a source, a date and a confidence level, one tap away.
- Sources are typed and visibly labelled: **Live API** · **Computed (OpenStreetMap)** ·
  **Official/Government** · **News/Media** · **Community-verified** · **Community-unverified** ·
  **Forum/Unverified**.
- Absence is shown as absence. "No verified water-supply data yet — be the first to report" is a
  valid, visible state, and it doubles as the community funnel.
- The scoring rubric and the persona weights are published in-app. A score the user cannot
  interrogate is a score they should not trust.
- The agent may never state a figure the Verifier did not pass. Unsourced reasoning is labelled as
  inference, visibly.

---

## 7. Community, live from day one

- **Contribution prompt on every report** — each thin module shows exactly what is missing and a
  one-tap way to fill it. This is how the cold start actually gets solved.
- **Experience posts** — free text, upvote/downvote, AI-assigned sentiment and topic tags, ranked
  with recency decay. Feed a "resident sentiment" signal only above a vote threshold, and always
  labelled as sentiment, never as fact.
- **Fact claims** — structured (water hours, outage frequency, noise, parking, water quality, rent
  actually paid). Require a photo or screenshot. Status: *pending → corroborated → verified*, or
  *disputed*. Needs independent corroboration from distinct users before the Scorer treats it as
  fact. Contradicting an official source raises a dispute, not an override.
- **Recognition** — contributor profile, streaks, and a locality leaderboard. Verified contributors
  earn free report credits. This is the cheapest possible growth loop and it directly buys the data
  the product is missing.
- **Abuse controls** — per-user rate limits, one vote per post, moderation queue, automated
  toxicity and PII screening before publication.

---

## 8. Freemium and Razorpay

- **5 full locality reports free**, per account, counted on first generation only. Re-opening an
  already-generated report is always free.
- **Regeneration counts** as a new report — it spends real money, so it is metered.
- **Chat is unlimited** inside an unlocked report, with a high anti-abuse daily ceiling.
- **Compare is premium** from first use. **Recommend** gets one free run.
- **Earned credits** — verified community contributions grant free reports.
- **Checkout runs on Razorpay in test mode** — real order creation, real checkout, real signature
  verification and webhook handling, with test cards. Switching to live is a key swap, not a rebuild.
- Plan tiers: Free · Pro monthly · Pro annual, priced in INR.

**Needed before build starts:** `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and a webhook secret from
the Razorpay dashboard (test mode). Everything else has its key already.

---

## 9. Cost and the rate-limit constraint

Groq's free tier for the `gpt-oss` models is roughly 30 req/min, 8,000 tokens/min and 200,000
tokens/day. A full multi-collector dossier is a large job — **under the free tier that permits only
a handful of fresh dossiers per day.**

The cached-dossier design is therefore a requirement, not an optimization:

- Dossiers are generated once per locality and shared across all users. ~25–30 Bangalore localities
  is a bounded one-time backfill, then only staleness-driven refreshes.
- Personalization, lens switching, chat and comparison run against the cached dossier — small
  prompts, well inside the limits.
- Deterministic work (distances, AQI banding, score arithmetic, unit conversion) never touches an LLM.
- Collector extraction uses the small fast model; only synthesis and comparison use the larger one.
- Built-in web search is billed per request, so search budgets are capped per dossier and searches
  are deduplicated and cached.

Marginal cost once warm: a fraction of a cent per personalized report and per chat turn. **If a paid
Groq tier is available, the initial Bangalore backfill drops from days to under an hour** — worth
confirming.

---

## 10. Quality, evaluation, traceability

In V1:
- **Golden set** — fixed localities with hand-checked ground truth for deterministic fields (AQI
  band, amenity counts, distances, score arithmetic), regression-checked so scoring cannot drift
  silently.
- **Groundedness check** — automated sampling of report claims against their cited source; any
  claim that cannot be traced back is a failure.
- **Full run traces** — per report: which agents ran, which tools were called, what each returned,
  token and search cost, latency. Inspectable.
- **Consistency check** — the same locality and persona generated twice must not produce
  contradictory scores; variance past a threshold is a defect.
- **Persona-sensitivity check** — module selection and weights must actually differ across personas.
  If a bachelor and a family get the same report, the core mechanic is broken.
- **Cost and latency dashboards** per report and per agent.

Designed for, deferred past V1: self-evolving prompt optimization, an offline simulation gym for
agent policies, automated A/B of rubric weights, LLM-as-judge scoring of narrative quality. All need
production traffic to mean anything, and all build on the traces V1 collects.

---

## 11. Privacy, safety, governance

- Profile data (work location, budget, household) is the most sensitive asset. Server-side only,
  never forwarded to third-party APIs, used only to condition module selection and narrative.
- Community posts are public by design, under a display name, with automated PII scrubbing before
  publication.
- All keys server-side. The browser never sees Groq, OpenWeather or Razorpay secrets.
- Agents call an explicit tool allow-list with validated arguments. No arbitrary code or database
  access from a model. Search queries are template-bounded, not free-form model output.
- Output rails: no claim that a locality is unsafe for a demographic, nothing that functions as
  discriminatory steering, no medical/legal advice, no investment guarantees. Reports carry a
  plain-language "decision support, not advice" disclaimer.
- Crime is presented as sourced, dated, media-reported incidents — never as a verdict about the
  people who live there.

---

## 12. Not in V1

- Cities beyond Bangalore.
- Google Maps / Places (revisit if a key with billing becomes available; the geodata layer is
  swappable).
- PDF export (ruled out by choice).
- Live payments (test mode only).
- Property listings, prices or transaction data.
- Native mobile apps — responsive web only.
- Self-improving agents and the simulation gym (§10).

---

## 13. Assumptions taken without asking

1. OpenStreetMap/Overpass for all distance and inventory questions; agentic web search for
   everything narrative. LLMs never compute distances.
2. Groq's built-in web search is the search layer — no Tavily/Brave/SerpAPI account needed.
3. ~25–30 Bangalore localities pre-warmed; anything outside generates live and is labelled
   **Provisional** with missing layers named.
4. Six persona presets ship, with manual module override available on every report.
5. The composite score is persona-weighted and always displayed with its persona label.
6. Regeneration spends a credit; re-opening does not.
7. Schools ship as inventory, distance and reputation-from-sources — not as an invented ranking.
8. Crime is labelled "media-reported incidents," explicitly distinct from crime rates.
9. Verified community contributions earn free report credits.

---

## 14. Worth pushing back on

- **Persona-weighted scores undercut the "credit score" pitch.** A score that changes per user is
  more useful but less comparable. The plan resolves this by also computing a neutral baseline score
  shown alongside the personalized one — confirm that is wanted, or drop it for simplicity.
- **Web-search crime is recency-biased.** A locality with heavy media coverage will look worse than
  an equally risky one nobody writes about. Presenting counts without that caveat would be worse
  than presenting nothing.
- **Search cost scales with regeneration.** If users regenerate freely, search spend grows linearly.
  Metering regeneration is what keeps this bounded — worth confirming that is acceptable UX.
- **Community still contributes ~nothing on day one.** It is built now so data accrues, but V1's
  value has to stand on live data plus web synthesis alone.
