# PurposeFit build guide

Nov 7, 2026 · @ALGO

## Decisions at a glance

PurposeFit is one container: a FastAPI backend that runs the privacy pipeline and serves a React front end built with IBM's Carbon Design System. Every choice below was checked against its licence and a working reference on 7 Nov 2026.

| Area | Choice | Licence | Why this one |
| --- | --- | --- | --- |
| Front end | React + Vite + TypeScript + `@carbon/react` | Apache 2.0 | A complete enterprise design system with a real DataTable; used in IBM's own security products, so it reads as a tool, not a template |
| Typeface | IBM Plex Sans and Plex Mono | SIL OFL 1.1 | Carbon's default typeface; free for commercial and web use |
| Backend | Python 3.11, FastAPI, pandas | MIT / BSD | The proving ground's `pets-eval` is Python, so we score with the organisers' own code |
| Validators | `python-stdnum` (HETU, IBAN, Luhn) | LGPL 2.1+ | Implements the HETU checksum and the century signs added in 2023 |
| Name gazetteer | DVV first name and surname lists | CC BY 4.0 | Official Finnish population name statistics, independent of the synthetic data |
| NER fallback | `fastino/gliner2-privacy-filter-PII-multi` | Apache 2.0 | Label-conditioned PII model, best span F1 on the SPY benchmark in its paper |
| Finnish NER backup | `Kansallisarkisto/finbert-ner` | MIT | Trained on Finnish; covers names, organisations, places |
| LLM (optional layer) | `gemini-3.6-flash` through the Gemini API, thinking off (default); `gemma-4-31b-it` and `LumiOpen/Llama-Poro-2-8B-Instruct` on Featherless (optional, env only) | Gemini API terms; Gemma Terms of Use; Llama 3.1 Community License | Fast, accepts thinking off, answered every call on 8 Nov 2026. The LLM step is optional and swappable; every release is also produced and verified with it switched off. |
| k-anonymity | Own full-domain generalisation search, verified with `pyCANON` and `pets-eval` | Apache 2.0 (pyCANON) | Interpretable bands judges can read; independent library confirms k |
| Hosting | Google Cloud Run + Secret Manager | Credit: $300 | Public link for judges, keys never in the image or repo |
| Security gates | gitleaks, ruff, bandit, pip-audit, npm audit, GitHub CodeQL, secret scanning, Dependabot, Claude Code `/security-review` | Free | Each covers a different failure: leaked keys, unsafe code, vulnerable dependencies |

**One rule above all:** the privacy pipeline is deterministic and testable; the LLM may label, flag or reword, but it never sets a parameter, never edits released data directly and never invents a number.

## Design: Carbon, used as shipped

Use IBM's Carbon Design System without restyling it. It is open source under Apache 2.0, its React package ships a full DataTable, and its look is that of enterprise security and data tools, which is exactly the trust signal a privacy product needs.

### The corner question

**Verdict: keep Carbon's square corners; do not add rounding.** Carbon sets a zero radius on tiles, tables, inputs and buttons by design, and design-system catalogues list it as the main square-cornered system next to shadcn's 4 to 12 px scale. Rounded cards everywhere are now the default look of AI-generated apps (shadcn, Lovable, v0), so rounding would work against your goal. Square corners also show the grid, which suits a dense data tool. If you want one creative signature, keep it to Carbon's own pill-shaped Tag for scenario and risk labels; that rounding is part of the system, not an override.

The concept screens on the PurposeFit canvas used rounded cards; treat them as layout only and build the look from Carbon.

### Setup

1. `npm create vite@latest web -- --template react-ts`, then `npm i @carbon/react @carbon/charts-react @carbon/icons-react sass`.
2. In `web/src/index.scss`: `@use '@carbon/react';` and wrap the app in `<Theme theme="g10">`. The UI Shell header stays dark (`g100`), as in Carbon's own examples.
3. Load IBM Plex through Carbon's styles; do not add another font.

### Components per screen

| Screen | Carbon components |
| --- | --- |
| Shell | `Header`, `HeaderName`, `SideNav`, `Content` |
| Steps (Data, Scenario, Plan, Verify, Export) | `ProgressIndicator` + `ProgressStep` |
| Scenario picker | `Tile` (selectable), `Dropdown`, `StructuredList` for recipient, purpose, attacker |
| Field inventory and plan | `DataTable` with `TableToolbarSearch`, `Tag` for role, `Tooltip` for the reason |
| Text redaction diff | Two `Layer`ed panels, `CodeSnippet` for placeholders, `Toggle` for placeholder or surrogate |
| Scorecard | `@carbon/charts-react` grouped bar (ours vs B2-k), `Tile` for each headline number |
| Release gate | `InlineNotification` (kind `success` or `error`) |
| Residual risks and policy card | `Accordion`, `Button` for downloads |

### Copy rules (no AI tone)

- Sentence case for every label and heading, as Carbon's guidelines do.
- No em dashes or decorative dashes. Use a full stop or a colon instead.
- No emoji, no sparkle icons, no gradients, no "magic" or "seamless".
- Every number carries its unit and its source: "7.6 % leakage, pets-eval, train split".
- Say what was measured, never "secure", "anonymous" or "GDPR compliant".
- Name techniques by their real names: keyed pseudonym (HMAC-SHA256), generalisation, k-anonymity (k = 5).

## Fact sheet: what the product may claim

The UI, report, README and pitch may state only the facts in this table, in these words or narrower. Put this table in the repo as `docs/FACTS.md` and tell every coding agent to use it.

| Topic | Verified statement | Source |
| --- | --- | --- |
| Pseudonymisation | GDPR Article 4(5) defines it as processing so data can no longer be attributed to a person without additional information kept separately. Pseudonymised data is still personal data (Recital 26) | GDPR; [EDPB Guidelines 01/2025](https://www.edpb.europa.eu/our-work-tools/our-documents/publication-type/guidelines_en) |
| EDPB guidance | The EDPB adopted Guidelines 01/2025 on pseudonymisation on 16 January 2025; public consultation closed 28 February 2025 | [EDPB](https://www.edpb.europa.eu/our-work-tools/our-documents/publication-type/guidelines_en), [Hunton](https://www.hunton.com/insights/publications/edpb-advises-on-pseudonymisation-for-gdpr-compliance) |
| Keyed pseudonym | HMAC-SHA256 with a secret key held only by the controller; without the key, a pseudonym cannot be recomputed from a guessed identifier | Standard HMAC property; matches the proving ground's `PET_PLAYBOOK.md` |
| Why not a plain hash | A HETU has a small, enumerable space; a public generator lists over 276 million valid codes, so an unkeyed hash can be reversed by trying them all. `pets-eval` runs this exact attack | [HETU generator](https://gist.github.com/ollipal/d27c33e011e45a6773870fea29279d91); `pets-eval` scorecard |
| HETU format | DDMMYY + century sign + individual number + check character. The check character is the 9-digit number mod 31 mapped to `0123456789ABCDEFHJKLMNPRSTUVWXY` | [python-stdnum fi.hetu](https://arthurdejong.org/python-stdnum/doc/stdnum.fi.hetu); [Finlex 690/2022](https://finlex.fi/api/media/statute/17253/mainPdf/main.pdf) |
| HETU century signs | `+` for the 1800s; `-`, `Y`, `X`, `W`, `V`, `U` for the 1900s; `A` to `F` for the 2000s. New signs in force from 1 January 2023; first new-sign code issued in December 2023 | [Valtioneuvosto](https://valtioneuvosto.fi/en/-/10623/availability-of-sufficient-personal-identity-codes-to-be-ensured-using-new-intermediate-characters); [Statistics Finland](https://stat.fi/meta/kas/hetu.html) |
| k-anonymity | Every combination of quasi-identifier values in the release is shared by at least k rows. It limits singling out on the stated quasi-identifiers only; it does not stop attribute inference inside a uniform group | Sweeney 2002, "Achieving k-anonymity privacy protection using generalization and suppression"; [pyCANON](https://pypi.org/project/pycanon/) |
| l-diversity | Each group must contain at least l well-represented values of the sensitive attribute; it addresses the homogeneity gap in k-anonymity | Machanavajjhala et al., ICDE 2006 |
| Workload-aware anonymisation | Quality should be judged against the tasks the data will serve | [LeFevre et al., KDD 2006](https://scilit.com/publications/13b4aefa68f67d8a19a33ee4660b2ba8) |
| Differential privacy | A mechanism is ε-DP if adding or removing one person changes any output's probability by at most a factor e^ε. Needs a stated unit, contribution bound and budget | Dwork et al. 2006; [OpenDP](https://github.com/opendp/opendp) |
| Text anonymisation | Removing predefined entity types is not enough; evaluation should weight recall and consider indirect identifiers | [TAB, Pilán et al. 2022](https://aclanthology.org/2022.cl-4.19) |
| LLM inference risk | LLMs infer personal attributes from text near human level; adversarial LLM feedback improves anonymisation | [Staab et al., ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f478b2e8ad9ff0756bf5b79fb31c330f-Abstract-Conference.html) |
| Proving-ground baselines | B2 regex redaction leaks 71 to 88 % of identifying values in free text; B2-k utility falls to 0.00 on HEALTH-S2 and CITY-S3 | `results/` in the proving ground, pets-eval 1.0.0 |

**Words the product never uses:** anonymous, anonymised, GDPR compliant, secure, guaranteed (except "ε-DP guarantee" when a DP mechanism with accounting actually ran).

## Backend: reference algorithms per module

Each module copies a published, working design rather than inventing one; the table names the reference to point Claude Code at.

| Module | Algorithm | Reference to copy | Our addition |
| --- | --- | --- | --- |
| Profiler | Per column: fill rate, distinct ratio, length stats, character classes, validator hit rate on a 2,000-row sample | ARX's risk analysis view; `pets-eval detect` output format | Validator hit rates from `python-stdnum` |
| Detector | Ordered rules on name tokens + profile, then LLM only for low-confidence columns with 20 sampled values | Proving ground baseline B1 (`baselines/`) as the floor to beat | Confidence and plain-language reason per column |
| Text redactor | Recogniser registry, context-word boosting, conflict resolution by score then length | [Presidio design](https://microsoft.github.io/presidio/design): recognisers, context enhancement, decision process | Spoken-digit and spelled-email normalisers; controller and DVV gazetteers; per-span `layer` tag |
| NER fallback | Label-conditioned span extraction on residual text | [GLiNER2-PII](https://arxiv.org/pdf/2605.09973), `pip install gliner2` | Run only on sentences with no rule hit; batch and cache |
| Health mentions | Sentence classification with an LLM, constrained JSON output | [Staab et al.](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f478b2e8ad9ff0756bf5b79fb31c330f-Abstract-Conference.html) adversarial loop, simplified | Gemma 4 31B on the Gemini API (Poro 2 on Featherless optional); cue-word prefilter keeps calls few |
| Scenario planner | Workload-aware minimisation: keep only columns a scenario task requires; HMAC on join keys | [LeFevre, Workload-aware anonymization](https://scilit.com/publications/13b4aefa68f67d8a19a33ee4660b2ba8) | Reads the proving ground's `scenarios.json` and task `requires` lists |
| Generalisation | Full-domain generalisation lattice: each QI has levels (e.g. age: exact, 5 y, 10 y, 80+ top-coded); enumerate all level combinations, keep those with k ≥ 5 after at most 2 % row suppression, pick the one with the best scenario utility | Incognito and [ARX Lightning](https://www.tdp.cat/issues16/abs.a223a15.php) | After minimisation only 2 to 4 QIs remain, so exhaustive search is a few hundred combinations |
| Alternative | Mondrian multidimensional partitioning | [Mondrian paper](https://personal.utdallas.edu/~mxk055100/courses/privacy08f_files/MultiDim.pdf); `polarfrost` row-preserving variant | Use only if lattice utility is poor |
| Independent check | k, l, t on the release | [pyCANON](https://pypi.org/project/pycanon/) (Scientific Data, 2022) | Shown in the UI next to pets-eval as a second opinion |
| Evaluation | Organisers' scorecard: linkage attacks, hash dictionary, HETU enumeration, MIA, utility tasks | `pets-eval` 1.0.0 in the proving ground | Same scenario and inputs for ours and B2-k |
| Text metric | Recall-weighted span scoring and value leakage | [TAB](https://aclanthology.org/2022.cl-4.19) evaluation idea; `pets_eval.text` | Ablation per layer |

### The redactor in order

1. **Validated patterns:** HETU (stdnum, all century signs), IBAN (mod 97), card (Luhn), Finnish phone, email, IPv4/IPv6, IMEI (Luhn), property ID, plates, URLs with tokens.
2. **Normalisers:** spoken digits in Finnish, Swedish and English mapped to digits, then re-checked by step 1; spelled emails ("dot", "piste", "punkt", "at", "ät", "snabel-a"); digit runs split across turns joined within a conversation.
3. **Gazetteers (Aho-Corasick):** values from columns the detector labelled direct identifiers, plus DVV first names (5 or more bearers) and surnames (20 or more bearers). Report the two sources separately so the synthetic-pool effect is visible.
4. **Cues:** "nimeni on", "jag heter", "my name is", relatives ("äitini", "my partner"), secrets ("salasana", "lösenord", "password", "PIN").
5. **NER:** GLiNER2-PII, then finbert-ner for Finnish if GLiNER misses on the test sample.
6. **Health:** LLM sentence flags (default Gemini 3.6 Flash), prefiltered by health cue words.
7. **Merge:** overlapping spans resolved by validator first, then longest span; each kept span stores `layer` and `score`.

**Test GLiNER2 on Finnish before relying on it.** Its model card lists 7 languages and does not confirm Finnish; run it on 200 train turns and compare recall with finbert-ner.

## Security and debugging toolchain

A privacy tool with a leaked key or a vulnerable dependency loses the argument on stage, so every layer below runs automatically and its green status goes in the README.

| Layer | Tool | What it catches | Where it runs | Setup |
| --- | --- | --- | --- | --- |
| Secrets before commit | gitleaks via pre-commit | API keys, HMAC key, tokens in staged files | Laptop | `pre-commit install` with the gitleaks hook |
| Secrets before push | GitHub secret scanning with push protection | Known token formats | GitHub | Free on public repos; Settings, Code security |
| Unsafe Python | bandit + ruff | Shell injection, weak hashing, bare excepts, unused code | pre-commit and CI | Hooks in `.pre-commit-config.yaml` |
| Code flaws | GitHub CodeQL default setup | Injection, path traversal, unsafe deserialisation | GitHub on every push | Settings, Code security, CodeQL, Default |
| Vulnerable dependencies | Dependabot alerts, `pip-audit`, `npm audit --omit=dev` | Known CVEs | GitHub and CI | Enable Dependabot; add both audits to CI |
| AI-assisted review | Claude Code `/security-review` and the `anthropics/claude-code-security-review` GitHub Action | Logic flaws: upload path traversal, SSRF, data written to logs | Laptop before each merge; CI on PRs | Run the command in the repo; add the action with your API key as a repo secret |
| Runtime secrets | Google Secret Manager mounted into Cloud Run with `--set-secrets` | Keys baked into images or env files | Cloud Run | `PURPOSEFIT_HMAC_KEY`, `GEMINI_API_KEY`, optional `FEATHERLESS_API_KEY` |
| Data in logs | Our own rule: log ids, counts and timings, never cell values or text | Accidental PII in Cloud Logging | Code review + a pytest that greps logs | `tests/test_no_pii_in_logs.py` |
| Upload safety | FastAPI: size cap (50 MB), CSV only, files written to a temp dir with random names, deleted after the run | Path traversal, zip bombs, disk fill | Backend | Covered by `/security-review` |

### Debugging aids built into the product

- **Run folders:** every stage writes `runs/<run_id>/NN_stage.json`; any stage reruns alone with `purposefit <stage> --run <id>`.
- **Leaderboard:** `runs/leaderboard.csv` gets one row per run (git hash, leakage, privacy, utility, composite), so a regression shows at once.
- **Span provenance:** each redaction carries its `layer`, so a false positive points to one rule or model.
- **Layer flags:** `--no-ner`, `--no-llm`, `--no-gazetteer` give the ablation table for free.
- **Structured logs:** JSON lines with `run_id`, `stage`, `duration_ms`, `rows_in`, `rows_out`.
- **Health endpoint:** `GET /api/health` reports model load status and versions; Cloud Run uses it as its startup probe.

## Phase 0: accounts, keys and repo (about 45 minutes)

Do these by hand before starting any agent; agents should never see real keys.

- [ ] Create a Gemini API key in Google AI Studio; confirm `gemini-3.6-flash` answers a test call (`uv run --env-file .env python -m scripts.check_llm`). Featherless is optional: its credits are used up
- [ ] Claim Google Cloud credit; create project `purposefit`; enable Cloud Run, Artifact Registry, Secret Manager, Cloud Build
- [ ] Create two secrets: `purposefit-hmac-key` (32 random bytes, `openssl rand -hex 32`) and `gemini-api-key`; `featherless-api-key` only if that provider is used
- [ ] Optional: ElevenLabs account for narration
- [ ] Public GitHub repo `purposefit`; enable secret scanning push protection, CodeQL default setup, Dependabot alerts
- [ ] Local `.env` (git-ignored) with the same names; `.env.example` committed with empty values

### Repo layout

```text
purposefit/
  CLAUDE.md                  rules for every agent (below)
  docs/FACTS.md              the fact sheet above
  docs/ARCHITECTURE.md       one diagram, one paragraph per module
  api/                       FastAPI app
    main.py                  routes, upload limits, static files
    pipeline/
      contracts.py           dataclasses shared by every module
      io.py profile.py detect.py plan.py transform.py
      redact/ patterns.py normalise.py gazetteer.py cues.py ner.py health.py merge.py
      generalise.py verify.py report.py llm.py
    cli.py                   purposefit run|profile|detect|... --run <id>
  web/                       Vite + React + Carbon
  data/gazetteer/            DVV name lists (CC BY 4.0, attribution in README)
  vendor/proving_ground/     unzipped archive, git-ignored
  runs/                      outputs, git-ignored; runs/private/ holds row maps
  tests/
  Dockerfile  Makefile  .pre-commit-config.yaml  .github/workflows/ci.yml
```

### CLAUDE.md (paste as is)

```markdown
# PurposeFit rules for coding agents
- Python 3.11, FastAPI, pandas. Read every CSV with dtype=str, keep_default_na=False.
- Shared types live only in api/pipeline/contracts.py. Change them only when asked.
- Inside api/: never read vendor/proving_ground/truth, metadata/pii_spans, metadata/field_catalog.csv or adversary/. Only tests/ and verify.py may.
- Row maps go to runs/private/ only. Never return them from the API, never log them.
- Logs contain ids, counts and timings only. Never cell values or text.
- Keys come from env: PURPOSEFIT_HMAC_KEY, GEMINI_API_KEY, optional FEATHERLESS_API_KEY. Refuse to start without the HMAC key.
- All LLM calls go through api/pipeline/llm.py, are logged by id and can be disabled with --no-llm.
- UI and report text may only state facts from docs/FACTS.md. No em dashes, no emoji, sentence case.
- Every task ends with: pytest green, ruff clean, a short note of what changed and how to verify it.
```

## Phases 1 to 10: build steps

Each phase has one prompt to paste into Claude Code (or Codex), a check you run yourself, and a rough time. Start a fresh agent session per phase and point it at `CLAUDE.md` and `docs/FACTS.md`. Phases 5 and 9 can run in a second terminal in parallel with 3 and 4.

### Phase 1. Skeleton, contracts, gates (1 h)

```text
Create the repo layout from docs/ARCHITECTURE.md. In api/pipeline/contracts.py define dataclasses:
ColumnProfile, FieldLabel(dataset, table, column, privacy_role, subtype, confidence, reason, source),
Span(record_id, start, end, label, layer, score), FieldPolicy(table, column, action, params, reason, guarantee),
PolicyPlan(dataset, scenario_id, released_tables, policies, k, key_id), ReleaseReport.
privacy_role and subtype must use the vocabulary in vendor/proving_ground/metadata/taxonomy.md.
Add cli.py with subcommands run, profile, detect, plan, transform, redact, verify, report, each taking --run.
Add .pre-commit-config.yaml (gitleaks, ruff, bandit), Makefile targets (test, lint, audit, demo),
and .github/workflows/ci.yml running ruff, pytest, pip-audit and npm audit. Write tests that import every module.
```

**Check:** `make test lint` green; `git commit` with a fake key in a file is blocked by gitleaks.

### Phase 2. Profile and detect (2 h)

```text
Implement profile.py and detect.py. Profile each column on up to 2,000 sampled rows: fill rate, distinct ratio,
length stats, character classes, and validator hit rates using python-stdnum (fi.hetu, iban, luhn).
Detect with ordered rules on column-name tokens (fi, sv, en) plus profiles; output FieldLabel with a one-line reason.
Write 02_labels.csv in the exact format pets-eval detect expects. Add a --llm flag that sends only low-confidence
columns (name + 20 sampled values) through llm.py and accepts the answer only if it is a valid taxonomy term.
Never read field_catalog.csv inside api/.
```

**Check:** `pets-eval detect` on the public catalog beats B1's macro-F1 of 0.65 and sensitive-attribute recall of 0.10. Run it on `data/unseen` and save the file for the organisers.

### Phase 3. Scenario planner and structured transforms (2 h)

```text
Implement plan.py: load scenarios.json and each utility task's requires list from pets-eval. Release only tables
and columns that a scenario task requires; withhold the rest and record why. Join keys that tasks need become
HMAC-SHA256 pseudonyms with PURPOSEFIT_HMAC_KEY, applied identically in every table. Direct identifiers not needed
are dropped and their values passed to the gazetteer. Implement transform.py to apply the plan, write
04_release/*.csv and runs/private/rowmap_*.csv.
```

**Check:** for CS-S1, `customers` is withheld, `conversation_id` matches across turns and conversations, CS-U1 is answerable, and `pets-eval check` reports zero residual identifiers in structured columns.

### Phase 4. Generalisation lattice and k check (2 h)

```text
Implement generalise.py: for each remaining quasi-identifier define levels (age: exact, 5 y, 10 y, 80+; postcode:
5, 3, 2 digits, dropped; timestamps: minute, hour, day, week; municipality: exact, region). Enumerate all level
combinations, keep those reaching k >= 5 after suppressing at most 2 % of rows, score each by the scenario's
pets-eval utility tasks, choose the best. Record the chosen levels and suppressed count in the plan. Verify k and
l with pyCANON and store both numbers.
```

**Check:** pyCANON's k equals the plan's k; HEALTH-S1 utility beats B2-k's 0.40.

### Phase 5. Redactor, rule layers (3 h)

```text
Port spike/redact_spike.py into api/pipeline/redact/ as separate recognisers: patterns, normalise, gazetteer, cues,
merge. Use python-stdnum validators. Load DVV name lists from data/gazetteer/ and controller values from the plan,
as two separate gazetteers. Every Span records its layer. Provide redact(texts, plan) -> spans, redacted_texts.
Add per-layer flags. Write unit tests with hand-made sentences in Finnish, Swedish and English for every label.
```

**Check:** CS train identifying leakage at or below the spike's 0.076 with precision at least 0.95; report leakage with the DVV gazetteer alone.

### Phase 6. NER and health layers (2 h)

```text
Add ner.py using gliner2 (fastino/gliner2-privacy-filter-PII-multi) on sentences with no rule hit, labels person,
street address, organisation, location. Add a finbert-ner fallback (Kansallisarkisto/finbert-ner) for Finnish.
Add health.py: prefilter sentences with health cue words, send them through llm.py (default provider gemini,
gemini-3.6-flash on the Gemini API, thinking off) asking for JSON {is_health: bool, span: str}; validate the span exists in
the sentence. Cache all model outputs by sentence hash.
```

**Check:** HEALTH leakage below 1.00 on train; total LLM calls per CS run logged and under the Gemini API rate limits for Gemini 3.6 Flash.

### Phase 7. Verify, leaderboard, ablation (1.5 h)

```text
Implement verify.py: run pets_eval.run_scorecard on our release and on baselines/protect.py --level b2k for the
same scenario; save both JSONs, compute the gate (zero residual direct identifiers, k >= 5, no risk component
above 0.2), append a leaderboard row, and produce an ablation table by rerunning redaction with each layer off.
```

**Check:** CS-S1 composite at or above 0.90; ablation table shows each layer's contribution.

### Phase 8. Report and policy card (1 h)

```text
Implement report.py: build a policy card per field and a residual-risk list from the plan and scorecards using
templates with numbers filled from JSON. Optionally pass the finished text through llm.py for plain-language
rewording, then reject the rewrite if any number or technique name changed. Facts only from docs/FACTS.md.
```

**Check:** every number in the report matches `06_scorecard_ours.json`.

### Phase 9. API and Carbon front end (4 h)

```text
API: GET /api/health, GET /api/scenarios, POST /api/runs (dataset id or CSV upload up to 50 MB, scenario id),
GET /api/runs/{id}, GET /api/runs/{id}/stages/{stage}, GET /api/runs/{id}/export (zip without row maps).
Run the pipeline in a background task; return progress per stage.
Web: Vite React TypeScript with @carbon/react, theme g10, UI Shell header. Screens: Scenario, Plan (DataTable
with Tag for role and Tooltip for reason), Text (two Layer panels, placeholder or surrogate Toggle), Verify
(@carbon/charts-react grouped bars ours vs B2-k, InlineNotification for the gate), Export. Use Carbon components
only, no custom border radius, sentence case, no em dashes. FastAPI serves web/dist.
```

**Check:** full CS-S1 click-through in under two minutes on cached runs; keyboard-only navigation works.

### Phase 10. Ship it (2 h)

```text
Write a multi-stage Dockerfile (node build, then python slim with the GLiNER2 weights baked in).
Deploy to Cloud Run with 4 GiB memory, --set-secrets for both keys, startup probe on /api/health.
Run /security-review, fix findings, and make sure CI, CodeQL and Dependabot are green.
Write pets_submission/ files for the unseen labels and CS eval redactions as EVALUATION.md specifies.
```

**Check:** the public URL works in a private browser window; the README shows green badges; organiser checks requested on Discord.

## Using the hackathon perks

Four perks go into the build; the rest stay out because they would add surface without adding score.

| Perk | Exact use | Setup |
| --- | --- | --- |
| Google AI Studio (Gemini API) | Default `llm.py` provider: `gemini-3.6-flash`, thinking off, for health flags, low-confidence column labels and report rewording | google-genai SDK with `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`; cache every valid response by input hash |
| Featherless ($25, used up) | Optional `llm.py` provider, model `LumiOpen/Llama-Poro-2-8B-Instruct` | OpenAI SDK with `base_url="https://api.featherless.ai/v1"` and `FEATHERLESS_API_KEY`, `LLM_PROVIDER=featherless` |
| Google Cloud ($300) | Cloud Run hosting, Secret Manager, Cloud Build | Region `europe-north1` (Finland), 4 GiB memory, min instances 1 during judging so the model is warm |
| ElevenLabs Creator | Narration for the demo video; stretch: a synthetic support call with a spoken HETU, transcribed and redacted live | Script from the demo section; voice only on synthetic content |
| Lovable Pro | Not for the product (Carbon is built by hand for consistency). Optional: a one-page landing site linking the demo and repo | Only if time remains |
| n8n Cloud Pro | Pitch slide only: "new export lands, PurposeFit runs, DPO approves in Slack" | None |
| Pruna AI, Copilot Student | Not used | None |

The LLM line for the pitch: The LLM step is optional and swappable; every release is also produced and verified with it switched off.

## Making it a stronger entry

The brief judges four things; each suggestion below targets one of them and costs at most two hours.

| Criterion (brief section 06) | Suggestion | Why it scores |
| --- | --- | --- |
| Technical implementation | Ablation table: leakage and utility with each redaction layer switched off | Proves each layer earns its place; judges see engineering, not a black box |
| Technical implementation | Second-opinion verification: pyCANON's k next to pets-eval's | Two independent tools agreeing is harder to dismiss |
| Innovation | Same dataset, two recipients: CS-S1 (vendor, transcripts) and CS-S3 (aggregate volumes) produce visibly different plans | Shows "context-aware" in one click, which is the challenge's core idea |
| Innovation | Controller gazetteer vs public DVV gazetteer reported separately | Turns the synthetic-name caveat into a measured finding |
| Impact | Request every organiser check: unseen labels, CS eval split, stronger hidden attacker; show the results even if worse | Independent evidence is the strongest impact claim available |
| Impact | Policy card mapped to EDPB Guidelines 01/2025 terms (pseudonymisation secret, domain, additional information) | Speaks the language of the DPO who would sign off |
| Presentation | One `make demo` command and a Docker image; README with architecture image, badges and limitations | Reproducibility is visible in the repo, which judges open |
| Presentation | Honest limitations screen inside the product, not only on a slide | Matches the brief's "honest limitations" requirement |
| All | A 30-second "before and after" opener: the same transcript, B2 output vs ours | The problem lands before any architecture |

**Avoid:** synthetic data generation, DP dashboards and trajectory privacy as side quests; they dilute the story and are already covered by baselines B3 and B4.

## Demo and submission checklist

The brief requires one working prototype, a short English demo video, a description and the repo or presentation on sinceai.app.

### Live demo, 4 minutes

1. **Problem (30 s):** one synthetic transcript; B2's regex output still shows the name, the spoken HETU and the spelled email.
2. **Scenario (20 s):** pick CS-S1, external analytics vendor.
3. **Plan (50 s):** the DataTable of fields, roles, techniques and reasons; `customers` withheld; switch to CS-S3 and show the plan change.
4. **Text (40 s):** side-by-side redaction with layer tags; toggle placeholders and surrogates.
5. **Verify (60 s):** gate notification, ours vs B2-k bars, pyCANON k, ablation table.
6. **Limits (30 s):** residual leakage per label, organiser results, pseudonymised data is still personal data.
7. **Close (10 s):** architecture image and public link.

### Video, 3 minutes

Record the live flow with OBS or QuickTime, add ElevenLabs narration from the script above, and burn in captions. Keep every number on screen identical to the run it came from.

### Submission

- [ ] Public Cloud Run URL tested in a private window
- [ ] Repo public, README with: problem, scenario, architecture image, how to run (`make demo`), results table vs B0/B2/B2-k, limitations, licences and DVV attribution
- [ ] CI, CodeQL, Dependabot green; `/security-review` run and findings closed
- [ ] `pets_submission/` sent; organiser results added to the README when they arrive
- [ ] No row maps, keys, `.env` or proving-ground truth files in the repo (`gitleaks detect` on the full history)
- [ ] Video uploaded, under the length the organisers set, English narration
- [ ] Description on sinceai.app copied from the README's first paragraph

## Sources

Checked on 7 Nov 2026. Challenge facts come from the challenge PDF, the FINAL\_REVIEW brief and the proving ground 1.0.0.

- Design: [Carbon Design System (Apache 2.0)](https://github.com/beaucalvez/carbon) · [@carbon/react DataTable](https://app.unpkg.com/@carbon/react@1.101.0/files/es/components/DataTable/DataTable.d.ts) · [Shape scale comparison, Carbon 0 px vs shadcn](https://meta.koder.dev/specs/themes/shape/) · [IBM Plex, SIL OFL](https://en.wikipedia.org/wiki/IBM_Plex)
- Law and guidance: [EDPB Guidelines 01/2025 on pseudonymisation](https://www.edpb.europa.eu/our-work-tools/our-documents/publication-type/guidelines_en) · [Hunton summary](https://www.hunton.com/insights/publications/edpb-advises-on-pseudonymisation-for-gdpr-compliance)
- HETU: [python-stdnum fi.hetu](https://arthurdejong.org/python-stdnum/doc/stdnum.fi.hetu) · [stdnum commit adding 2023 century signs](https://lists.arthurdejong.org/python-stdnum-commits/2023/msg00011.html) · [Valtioneuvosto announcement](https://valtioneuvosto.fi/en/-/10623/availability-of-sufficient-personal-identity-codes-to-be-ensured-using-new-intermediate-characters) · [Statistics Finland definition](https://stat.fi/meta/kas/hetu.html) · [Finlex decree 690/2022](https://finlex.fi/api/media/statute/17253/mainPdf/main.pdf) · [HETU generator](https://gist.github.com/ollipal/d27c33e011e45a6773870fea29279d91)
- Names: [DVV Finnish name data on avoindata.fi](https://www.avoindata.fi/data/en/dataset/none)
- Algorithms: [Presidio design](https://microsoft.github.io/presidio/design) · [GLiNER2-PII paper](https://arxiv.org/pdf/2605.09973) · [GLiNER2-PII model card mirror](https://huggingface.co/mateoopa/gliner2-privacy-filter-PII-multi) · [finbert-ner](https://huggingface.co/Kansallisarkisto/finbert-ner/blob/main/README.md?code=true) · [pyCANON](https://pypi.org/project/pycanon/) · [Mondrian](https://personal.utdallas.edu/~mxk055100/courses/privacy08f_files/MultiDim.pdf) · [polarfrost](https://pypi.org/project/polarfrost/) · [Workload-aware anonymization](https://scilit.com/publications/13b4aefa68f67d8a19a33ee4660b2ba8) · [ARX Lightning](https://www.tdp.cat/issues16/abs.a223a15.php) · [TAB benchmark](https://aclanthology.org/2022.cl-4.19) · [Staab et al., ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f478b2e8ad9ff0756bf5b79fb31c330f-Abstract-Conference.html) · [OpenDP](https://github.com/opendp/opendp)
- Models and services: [Gemma on the Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api) · [Featherless API reference](https://featherless.ai/docs/api-reference) · [Poro 2 8B Instruct on Featherless](https://featherless.ai/models/LumiOpen/Llama-Poro-2-8B-Instruct) · [Poro 2 release](https://www.amd.com/en/blogs/2025/silo-ai-continued-pretraining-provides-blueprint-for-gla.html) · [Cloud Run secrets](https://cloud.Google.com/run/docs/configuring/secrets)
- Security: [Claude Code security review](https://support.claude.com/en/articles/11932705) · [gitleaks with pre-commit and CI](https://www.kunalganglani.com/blog/gitleaks-pre-commit-ci-setup) · [GitHub code security docs](https://docs.github.com/en/code-security/reference) · [Push protection free on public repos](https://github.blog/search/REST%20API/page/9)
