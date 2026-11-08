# PurposeFit landing experience brief (adds to UI_BRIEF.md)

The current screens are correct but feel like a data tool on first sight. Judges decide in seconds. Add a landing experience in front of the existing app. The existing screens stay, renamed "Workbench", and are reached from the landing page.

This brief overrides two lines of UI_BRIEF.md: a large hero headline is now wanted, and the landing page may use more white space and larger type than the workbench. Everything else in UI_BRIEF.md still applies: Carbon, IBM Plex, square corners, no gradients, no glow, no sparkle icons, no emoji, no em dashes, sentence case, every number read from data with its source.

## Structure

Two views, switched by the URL hash, no new routing library:
- `#/` the landing page (default)
- `#/workbench` the existing five screens, unchanged in behaviour

## Landing page: five full-screen sections that slide over each other

Each section is a full viewport panel. As the visitor scrolls, the next panel slides up and covers the previous one (stacked sticky panels). Scrolling is smooth.

### 1. Hero (dark, Carbon g100)
- Very large product name "PurposeFit" (Carbon fluid display type, IBM Plex Sans Light or Regular).
- One headline: "Share data for a purpose. Prove it is safe to share."
- One short line under it: "PurposeFit decides what each recipient needs, protects the rest, and re-runs real privacy attacks before anything leaves your hands."
- Two buttons: primary "See how it works" (scrolls to section 2), secondary "Open the workbench" (goes to `#/workbench`).
- One proof line at the bottom, read from the leaderboard fixture: "Support transcripts to an external AI vendor: overall score 0.98 vs 0.58 for the classic baseline · pets-eval".
- Nothing else. No illustration.

### 2. The problem (white): three facts, one line each
Three large numbers in a row, each with one sentence and a small source line:
- Share of identifying values left in transcripts by regex redaction (from the fixtures, about 80 %): "Removing names is not enough. People say ID numbers aloud and spell out emails."
- The c20 finding from findings.json: "A column called pseudonymised was the national ID, hashed. Anyone can reverse it."
- The baseline's broken intent-model task: "Blind protection breaks the analysis it was meant to allow."

### 3. How it works (light gray, Carbon g10): four steps
Four equal tiles in a row, each with a Carbon pictogram or icon, a two-word title and one sentence:
1. Detect: "Finds what every column and sentence contains."
2. Plan for the purpose: "Keeps only what the recipient's task needs."
3. Protect: "Pseudonymises keys, coarsens what identifies, removes identifiers from text."
4. Verify: "Re-runs the organisers' attacks. No pass, no export."

### 4. Pick a recipient (white): three or four option tiles
Minimal tiles, each with: recipient name, one line on purpose, what is released (for example "Conversations and redacted transcripts"), and one score with its baseline. Read all of it from the scenario, plan and leaderboard fixtures. Clicking a tile opens `#/workbench` with that scenario selected.
- CS-S1 external AI vendor
- CS-S3 quality-audit partner
- Unseen HR export: detection only (26 columns found from values alone)

### 5. Results and honest limits (dark, g100)
- One grouped bar chart: PurposeFit vs B2-k on privacy, utility, overall for CS-S1 and CS-S3.
- Three short limitation lines from the fixtures' residual risks (for example: pseudonymised data is still personal data; results are on synthetic data; name matching also uses the company's own records, public-name-only result shown).
- A final call to action: "Open the workbench".
- Footer: project name, TrustED PETs Transformer challenge, Since AI Hackathon 2026, links to the GitHub repo and the README.

## Motion

- Stacked panels with CSS only: each section `position: sticky; top: 0; min-height: 100vh`, increasing `z-index`, so the next one slides over the previous. Use a subtle shadow on the top edge of the incoming panel, not a blur.
- Smooth scrolling with the Lenis library (MIT licence, about 3 kB). Initialise it only on the landing view and destroy it when leaving.
- Section content fades in and rises 16 px once when it enters the viewport (IntersectionObserver, no animation library).
- Respect `prefers-reduced-motion`: no Lenis, no fade, panels scroll normally.
- Keep all motion values in `web/src/landing/landing.scss` as CSS custom properties at the top (duration, easing, rise distance, shadow) so they can be tuned by hand.

## Workbench changes

- Add a small "PurposeFit" home link in the header that returns to `#/`.
- The scenario chosen on the landing page preselects in the workbench.
- No other changes.

## Files

- `web/src/landing/Landing.tsx` and one component per section in `web/src/landing/sections/`.
- `web/src/landing/landing.scss` with the tunable motion variables at the top.
- Only new dependency allowed: `lenis`.

## Quality bar

- First screen readable in 3 seconds: name, headline, one proof number, two buttons.
- Works at 1440, 1280 and 390 px wide. On phones the panels stack without the sticky effect.
- Keyboard: buttons and tiles reachable, visible focus.
- `npm run build` passes; `npm audit --omit=dev` has no high or critical findings.
- Commit on branch `ui` and push. Report what you built and how to tune the motion.
