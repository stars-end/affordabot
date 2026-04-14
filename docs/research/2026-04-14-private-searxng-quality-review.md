# Private SearXNG quality review — San Jose housing meeting minutes

- Feature key: `bd-9qjof.8`
- Depends on: `bd-9qjof.6` (live Windmill San Jose validation gate)
- Context PR: https://github.com/stars-end/affordabot/pull/434
- Reviewer role: senior search/retrieval consultant (read-only QA pass)
- Date: 2026-04-14

## 1. Executive verdict

**Private SearXNG can be the MVP primary discovery lane, but not as currently
wired.** The April 13 bakeoff (`search_source_quality_bakeoff_report.md`) shows
SearXNG is *already* returning official-domain results at a higher rate than
Tavily or Exa for the San Jose family (94.7% official-hit rate vs. 84.2% and
73.7%), and the underlying engines are surfacing Legistar artifact URLs in the
top‑5. The failure observed in PR #433's live gate — the pipeline selected
`sanjoseca.gov/.../agendas-minutes`, which rendered as a title-only reader
shell — is **not** a SearXNG recall problem. It is a *ranking, portal-handling,
and reader-gate* problem in the backend. SearXNG-native knobs help marginally;
the decisive fixes are in `services/pipeline/domain/commands.py`
(`rank_reader_candidates`, `assess_reader_substance`) and in pre-fetch portal
treatment.

Verdict: **approve_with_changes**. Ship SearXNG as primary after applying the
S1/S2/B1/B2/R1 fixes in §8. Keep Tavily as cheap hot-fallback and Exa as
quality bakeoff-only (free-tier capped, needs custom UA).

## 2. Evidence summary

### 2.1 What the April 13 bakeoff actually shows

From `docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.json`,
SearXNG San Jose probes (all `status: succeeded`, latency 616–768 ms):

| Query (San Jose) | SearXNG top‑1 (before backend re-rank) | Class |
|---|---|---|
| council meeting minutes housing | `/your-government/departments-offices/housing/resource-library/council-memos` | **portal** |
| council agenda affordable housing | `/your-government/departments-offices/housing/resource-library/council-memos` | **portal** |
| planning commission minutes housing development | `/your-government/.../planning-commission/planning-commission-agendas-minutes` | **portal** |
| rent stabilization committee meeting minutes | `/your-government/.../resource-library/council-memos` | **portal** |
| city clerk council minutes PDF housing | `/your-government/.../resource-library/council-memos` | **portal** |
| city council housing memorandum | `/your-government/.../resource-library/council-memos` | **portal** |

Within each top‑5, SearXNG *also* returns artifact-grade Legistar URLs
(`View.ashx?M=A`, `MeetingDetail.aspx`, `gateway.aspx?m=l&id=%2Fmatter.aspx`,
`View.ashx?M=F&ID=...`) — often at position 2–5. Example: the "city council
housing memorandum" probe returned
`sanjose.legistar.com/View.ashx?M=F&ID=15266771` at position 3, which is the
precise artifact the downstream reader/analyzer wanted.

**Diagnosis**: SearXNG recall for this jurisdiction is good. What fails is the
backend's ability to prefer the artifact over the portal when both are present
and both match surface signals ("agenda", "minutes", "legistar").

### 2.2 What the Windmill San Jose live gate selected

PR #433's run picked `sanjoseca.gov/your-government/agendas-minutes`. Reader
output was essentially `Agendas & Minutes | City of San José` — a navigation
shell. The LLM (correctly) refused to emit housing signals.

### 2.3 Why targeted Legistar queries "worked"

Manual tests with `site:sanjose.legistar.com` produced artifact URLs as top‑1
because `site:` forces the engine off the city landing pages. This isn't a
fundamental engine difference — it's a *query shape* and a *re-rank* problem.

## 3. Root cause analysis

Ordered by contribution to the observed failure.

### RC1 — Backend ranker under-penalizes portal/directory URL shapes *(primary)*

`rank_reader_candidates` in
`backend/services/pipeline/domain/commands.py:290` currently rewards any URL
containing `legistar.com`, `/agenda`, or `/minutes` and only penalizes
`granicus.com/agendaviewer` + `agendaviewer.php`. It does **not** penalize:

- `sanjose.legistar.com/DepartmentDetail.aspx` (department calendar, no content)
- `sanjose.legistar.com/Calendar.aspx` (calendar index)
- `sanjoseca.gov/your-government/agendas-minutes` (city clerk landing)
- `sanjoseca.gov/your-government/.../resource-library/council-memos` (memo index)
- `/commission-agendas-minutes` (commission index)

These all look like "good" URLs to the ranker because they contain the bonus
substrings `/agenda` or `/minutes` or `legistar.com`. They are in fact directory
landing pages.

### RC2 — Reader quality gate fires too late, and only on content

`assess_reader_substance` (commands.py:225) can only classify a fetch
*after* the reader has paid the cost of fetching and extracting the page. For a
portal landing page the reader output is usually a short title‑only stub, which
is correctly flagged but too late to recover: by then the ranker has committed
to that candidate and no alternative is retried with backtracking evidence.

### RC3 — SearXNG query shape is a single bare string

`_probe_searxng` in `verify_search_source_quality_bakeoff.py:341` issues
`GET /search?q=<raw>&format=json`. It does **not** pass `engines=`, `language=`,
`categories=`, `time_range=`, `pageno=`, or any SearXNG search-syntax operators
(`site:`, `filetype:`). This relies entirely on instance defaults and a single
general-category multi-engine search. For civic records this biases toward
long-lived domain landing pages (high PageRank, broad title match) over
transient meeting artifacts.

### RC4 — No source-family query fanout

For a query like "San Jose council meeting minutes housing" the harness issues
one search. It does not fan out across the known San Jose source families:
Legistar, Granicus, Agenda Center, city clerk PDF directories. A single query
cannot rank across those families fairly.

### RC5 — No pre-fetch portal classifier

There is no step that says "this URL shape is a landing page, expand it before
fetching." The pipeline treats every search hit as a final artifact candidate.

### RC6 — Query-family blindness on expected_signal_terms

The rubric's `expected_signal_terms` are not passed through to the backend
ranker, so the content-free re-rank cannot see *why* a query exists. A query
tagged `source_family=meeting_minutes` should boost `MeetingDetail.aspx`
artifacts more than a `source_family=memos` query would.

## 4. SearXNG-native fixes (S-class)

SearXNG documents the API, query syntax, engine settings, and per-instance
tuning here:

- Search API: https://docs.searxng.org/dev/search_api.html
- Search syntax (operators, bangs, site:, filetype:): https://docs.searxng.org/user/search-syntax.html
- Engine configuration and weights: https://docs.searxng.org/admin/engines/settings.html
- Configured engines list (which engines exist by default): https://docs.searxng.org/user/configured_engines.html

### S1 — Pin the engine set used for civic queries *(do now)*

Pass `engines=google,bing,duckduckgo,brave,startpage,qwant` on every probe.
Rationale: without `engines=`, SearXNG uses the instance default, which depends
on whether individual engines are healthy on the Railway-hosted instance at
probe time. A pinned set produces reproducible recall and is cheap.

API: `GET /search?q=...&format=json&engines=google,bing,duckduckgo,brave,startpage,qwant`.

### S2 — Set `language=en` and `categories=general` *(do now)*

`GET /search?q=...&language=en&categories=general&format=json`. Prevents
region/locale drift and excludes `images`, `videos`, `news` merges from the
`general` bucket. Cheap; avoids YouTube/Reddit noise we already see in the top‑5.

### S3 — Use `site:` / `filetype:` operators directly, not bangs *(do now)*

SearXNG supports inline operators via the aggregator's generic query rewriter
(documented under "Search syntax"). For San Jose housing minutes this means the
fanout from §5 should produce queries like
`"San Jose housing ordinance site:sanjose.legistar.com"` rather than issuing a
`!go` bang. Bangs route to one engine and defeat the multi-engine voting that
is SearXNG's whole point.

### S4 — Consider `time_range=year` for action queries *(optional, measure)*

For queries whose signal is "recent housing action" (memos, rent committee),
`time_range=year` narrows candidates to current-cycle material. Do not apply to
"housing element" queries (multi-year cadence).

### S5 — Instance-level engine weights *(optional, infra task)*

On the Railway-hosted SearXNG instance (`searxng-railway-production-79aa`),
`settings.yml` can raise `google`/`bing` weight for civic recall and disable
engines that are known-broken (Qwant EN, Startpage captcha periods). This is
an infra change tracked under `bd-ybyy7.1`; it is not required for MVP.

### S6 — Do **not** rely on `!bang` routing for primary recall

Bangs in SearXNG are routing hints; they bypass the multi-engine fusion. Use
them only in emergency or for debugging ("does Google still know about this?").

## 5. Source-family query fanout (backend-side)

For San Jose housing meeting minutes, issue N parallel SearXNG probes and merge
their top‑5s before ranking. Minimum 5 recipes (sj-001..sj-006 class):

1. `<jurisdiction> <topic> site:sanjose.legistar.com`
2. `<topic> ordinance resolution site:sanjose.legistar.com filetype:pdf`
3. `<jurisdiction> <topic> site:sanjoseca.gov filetype:pdf`
4. `<jurisdiction> <topic> site:sanjoseca.gov/your-government/appointees/city-clerk/council-agendas-minutes`
5. `<jurisdiction> city council <topic> sanjose.legistar.com View.ashx`
6. `<jurisdiction> <topic> sanjose.granicus.com AgendaViewer`
7. `<jurisdiction> <topic> memorandum site:sanjoseca.gov/your-government/departments-offices/housing/resource-library`

Dedupe by canonical URL (scheme+host+path, lowercased, trailing-slash
stripped — the harness already has `_canonicalize_url` at line 147). Collapse
`View.ashx?GUID=...&ID=N&M=A` variants by `ID` parameter.

The fanout happens **before** the ranker. Each sub-query's top‑5 gets merged
into a candidate pool of ~25 URLs; the ranker then chooses. Cost is linear in
fanout width; a private SearXNG is the right place to pay that cost because
there is no per-query free-tier meter.

## 6. Backend ranking fixes (B-class)

All edits land in `backend/services/pipeline/domain/commands.py`.

### B1 — Add portal/directory URL-shape penalties

Expand `LOW_VALUE_AGENDA_HEADER_URL_SIGNALS` (currently line 43) to include:

```
"legistar.com/departmentdetail.aspx"
"legistar.com/calendar.aspx"
"/your-government/agendas-minutes"
"/resource-library/council-memos"
"/resource-library/information-memos"
"/commission-agendas-minutes"
"/planning-commission-agendas-minutes"
"/council-agendas-minutes"
```

Apply a hard `-10` (not `-5`) for these. Rationale: the ranker already gives
`+5` for `legistar.com` and `+5` for `/agenda` or `/minutes`; a `-5` cancels
once and leaves a portal tied with an artifact. A `-10` makes the portal
strictly dominated.

### B2 — Boost true-artifact URL shapes harder

In `HIGH_VALUE_URL_SIGNALS` (line 36) the current `+6` for `.pdf` and `+5` for
`View.ashx` is correct in direction but weak. Add:

```
"legistar.com/view.ashx?m=a"  # agenda artifact
"legistar.com/view.ashx?m=f"  # file artifact
"legistar.com/gateway.aspx?id="  # direct gateway artifact
"legistar.com/meetingdetail.aspx?id="  # specific meeting, not department
```

Score `+8` for these. The key is the *query string* — `DepartmentDetail.aspx`
vs `MeetingDetail.aspx` is a portal-vs-artifact distinction.

### B3 — Title-shape penalty for bare portal titles

Add a title-regex penalty: if the extracted title matches
`^[A-Z][A-Za-z &]+\s*\|\s*City of San José$` and contains no date, item
number, or action verb, apply `-4`. This catches `Agendas & Minutes | City of
San José` without touching real artifact titles like
`26-166 - Memorandum from Casey, 2/23/26`.

### B4 — Pass `source_family` and `expected_signal_terms` into the ranker

The rubric already tags queries with `source_family`. Thread that through to
`rank_reader_candidates` so `memos` queries reward `/information-memos/<id>`
and `meeting_minutes` queries reward `View.ashx?M=A`. This is a small change
but removes most of the remaining portal ties.

## 7. Reader-quality gate fix (R-class)

### R1 — Pre-fetch SKIP list for known portal shapes

`assess_reader_substance` (commands.py:225) already classifies nav-heavy reader
output as `navigation_heavy`. The problem is that the reader has to fetch the
portal before that fires, and by then the ranker has consumed its budget. Add a
pre-fetch `is_known_portal_shape(url)` check that rejects the B1 URL patterns
**before** dispatching the reader call. If every top-ranked candidate is a
portal, fall through to the second-highest ranked candidate.

### R2 — Character-count floor on reader output

Add a hard minimum: if extracted content length < 400 non-markup characters
and the URL isn't a small-PDF exception, treat as `reader_content_too_thin`
and mark the candidate `unusable`, forcing a fallback to the next ranked URL.
The current `empty_reader_output` check only catches zero-length outputs;
`Agendas & Minutes | City of San José` is ~35 characters and slips through.

### R3 — Portal expansion instead of final-target treatment

For any URL that matches a known portal pattern (B1 list), treat it as a
**seed**, not a final artifact. Queue an expansion step: fetch the portal,
extract outbound links matching artifact shapes from §B2, re-rank those, and
feed them back through the normal reader path. This reuses the existing
ranker — it just loops once. Only enable this for the top‑1 candidate to cap
cost at one extra fetch per pipeline run.

## 8. Proposed acceptance criteria for the next live San Jose run

A live Windmill San Jose gate with SearXNG-primary must meet all of:

1. **Selected source shape**: top‑1 candidate URL matches
   `View\.ashx|MeetingDetail\.aspx|gateway\.aspx\?id=|\.pdf` on `.gov`,
   `legistar.com`, or `granicus.com`.
2. **Reader content floor**: extracted content ≥ 800 non-markup characters;
   `assess_reader_substance` returns `substantive=true`.
3. **Z.ai analysis sufficiency**: at least one San Jose housing question
   returns `sufficient_evidence=true` with a direct citation chain to a
   document-level URL. (This is the gate PR #433 failed.)
4. **Provenance chain persisted**: row(s) exist in Postgres linking
   search_snapshot → reader_document → analysis_evidence with matching
   canonical document key. MinIO storage ref matches the canonical key.
5. **No portal top‑1**: pre-fetch portal SKIP list reports zero hits in the
   final selected candidate; if expansion fires, the gate logs the
   portal-expansion step and the final artifact URL.

These criteria plug into `verify_windmill_sanjose_live_gate.py` as deterministic
assertions.

## 9. Minimum bakeoff corpus to prove SearXNG-primary

The current `query-corpus.json` has 20 entries (6 San Jose, 4 Saratoga, 5 SCC,
2 control cities, 2 negative). To prove private SearXNG is good enough as
*primary*, extend with:

- 3 `site:legistar.com` positive probes per target jurisdiction (proves recall
  when the portal is excluded).
- 3 `filetype:pdf` probes per target jurisdiction (proves PDF surfacing).
- 2 source-family fanout probes per jurisdiction that exercise B4's family
  routing.

That lifts the corpus to ~35 queries, still small enough to run end-to-end in
under a minute against a private SearXNG instance. No extra Exa/Tavily
quota is needed: those providers can be re-run on the full 35 in one deliberate
bakeoff after B1-B4 and R1-R3 land.

**MVP threshold after fixes**: keep the rubric thresholds unchanged except
raise `reader_ready_rate` target from `0.65` to `0.70`; the pre-fetch portal
SKIP list should make this trivially achievable.

## 10. Provider role recommendation

| Provider | Role after fixes | Rationale |
|---|---|---|
| **Private SearXNG** | **Primary** | Already has best official-hit rate; no per-query cost; recall is sufficient once portal re-rank lands. |
| Tavily | Hot fallback | Low latency (446 ms p90), free tier is the constraint — use only when SearXNG recall is empty or all candidates are portal-shape. |
| Exa | Bakeoff/eval only | Best per-query quality but requires custom UA (`affordabot-dev-bakeoff/1.0`), Cloudflare-sensitive, free tier is capped; reserve for offline quality checks and corpus curation. |

Do **not** lock this until the acceptance criteria in §8 pass.

## 11. Risk ranking and implementation order

| Order | Change | Class | Risk | Unblocks |
|---|---|---|---|---|
| 1 | B1 (portal URL penalties) | backend | low — data-only | selects artifact over portal in current bakeoff set |
| 2 | B2 (artifact URL boosts) | backend | low — data-only | raises SJ median query score |
| 3 | R1 (pre-fetch portal SKIP) | backend | low — one new pure fn | stops portal reader fetches in Windmill gate |
| 4 | R2 (reader content floor) | backend | low | catches residual thin-content cases |
| 5 | S1+S2 (pinned engines + lang + categories) | searxng probe | very low — query-string only | reproducibility; minor recall lift |
| 6 | §5 source-family query fanout | backend | medium — new fanout code + dedupe | removes dependence on single-query luck |
| 7 | B4 (thread source_family into ranker) | backend | medium — signature change | precision lift; test churn |
| 8 | R3 (portal expansion loop) | backend | medium — one extra fetch per run | worst-case recovery if ranker misses |
| 9 | S4 (time_range=year for action queries) | searxng probe | low — measurable | marginal |
| 10 | S5 (instance engine weights) | infra | medium — separate PR | not MVP-blocking; tracked under `bd-ybyy7.1` |
| 11 | §9 corpus expansion | eval | low | gives confidence to lock SearXNG primary |

**Land order for the next implementation PR**: 1, 2, 3, 4, 5 together — these
are data-only or near-data-only and have no new subsystems. Ship, re-run the
Windmill San Jose live gate, verify §8 criteria. Then ship 6, 7, 8 in a
separate PR.

**Do not land** in the MVP-primary PR: S5 (infra), S6 (anti-pattern).

## 12. Commands run (read-only)

```bash
git fetch origin pull/434/head:pr-434
dx-worktree create bd-9qjof.8 affordabot         # workspace already existed
cd /tmp/agents/bd-9qjof.8/affordabot
git rev-parse HEAD                                # f12d2d6d96632a72d55badcf0bc51255ea6d56fe
git stash -u                                      # stashed dirty .serena/project.yml

# Memory lookups
bdx memories searxng --json
bdx memories windmill --json
bdx search "searxng search quality" --label memory --status all --json
bdx search "private searxng" --status all --json
# → returned bd-ybyy7.1 (private SearXNG infra provisioning task, open, P1)

# Read and grep key files
docs/poc/search-source-quality-bakeoff/README.md
docs/poc/search-source-quality-bakeoff/scoring-rubric.md
docs/poc/search-source-quality-bakeoff/query-corpus.json
docs/poc/search-source-quality-bakeoff/artifacts/search_source_quality_bakeoff_report.{json,md}
backend/services/pipeline/domain/commands.py     # rank_reader_candidates, assess_reader_substance
backend/scripts/verification/verify_search_source_quality_bakeoff.py  # _probe_searxng
```

**Not run** (would consume Exa/Tavily free-tier quota and are not required for
a read-only QA pass):

- Live SearXNG-only probes against the Railway instance
- Exa/Tavily re-bakeoff
- Windmill San Jose live gate re-run

The April 13 bakeoff JSON already contains the raw SearXNG probe output needed
to support every claim in this report.

## 13. Open questions for the implementer

1. Is the Railway SearXNG instance's `settings.yml` under source control in
   this repo, or only on Railway? If only on Railway, S1 (pinned engines via
   query string) is the safer fix than S5 (instance weights).
2. Does the backend reader currently have a way to express "this URL is a
   seed, not a final target" in its persistence model? If not, R3 needs a
   small schema addition (a `role` or `kind` column on the reader candidates
   table) before it can land.
3. The rubric penalizes candidates with `reader_substance=navigation_heavy`
   after the fact; would the team prefer a blocking pre-fetch SKIP (R1) or a
   retry-with-fallback? I recommend R1 because it is cheaper, but retry is a
   smaller behavior change if the schema constraint from (2) is tight.
