# PurposeFit landing page v2 brief (approved design)

This replaces docs/LANDING_BRIEF.md for the landing page only. The workbench (`#/workbench`) stays exactly as it is. Read docs/UI_BRIEF.md for the copy rules, which still apply.

## Scope and timing

- Work on branch `ui` in ~/PurposeFit-ui. First run `git merge main` so you have the final fixtures and the merged code. Resolve nothing outside `web/src/landing/`; if a conflict appears elsewhere, stop and report.
- Edit only `web/src/landing/**` and, if needed, add shared landing components under `web/src/landing/components/`. Do not change `api.ts`, `types.ts`, the workbench screens or the backend.
- Hard stop at 06:15. If something in this brief does not fit, ship the sections in order 1, 4, 5, 3, 2, 6, 7 and report what was left out.

## Positioning

A serious B2B privacy technology company site: light, editorial, product-led. Not an AI startup template, not a game, no feature-card grids. Use cases come before features. The real product is the main visual.

## Visual system

| Token | Value | Use |
| --- | --- | --- |
| `--pf-bg` | `#FAF8F3` warm ivory | page background |
| `--pf-surface` | `#FFFFFF` | cards, product frames |
| `--pf-line` | `#E4E0D8` | 1 px borders, dividers |
| `--pf-ink` | `#1C2430` | headings, body |
| `--pf-muted` | `#5A6472` | captions, source lines |
| `--pf-accent` | `#0E7C7B` teal | links, highlights, PurposeFit series in charts |
| `--pf-accent-tint` | `#E6F2F1` | highlighted rows, subtle fills |
| `--pf-pass` | `#1F7A4D` | gate passed only |
| `--pf-block` | `#B42318` | gate blocked only |
| `--pf-radius` | `4px` | landing cards and frames (workbench keeps Carbon square corners) |
| `--pf-shadow` | `0 1px 2px rgba(28,36,48,.06), 0 8px 24px rgba(28,36,48,.06)` | product frames only |

- Type: IBM Plex Serif for H1 and H2; IBM Plex Sans for body and UI; IBM Plex Mono for column names, values and run ids. Load Plex Serif from the `@ibm/plex` package or Google Fonts (SIL OFL).
- H1 clamp(44px, 6vw, 76px), H2 clamp(32px, 4vw, 48px), body 18px/1.6, captions 13px.
- 8 px spacing grid; sections at least 120 px vertical padding; max text width 64 characters.
- Teal is the only accent. No gradients, glow, glassmorphism, emoji, sparkle icons, stock images or abstract illustrations.

## Sections (each a full-height sticky panel)

1. **Hero.** Left: H1 "Share data with purpose. Protect what matters." One subhead line: "PurposeFit decides what each recipient needs, protects the rest, and re-runs real privacy attacks before anything is released." Buttons: "See how it works" (scrolls to section 3) and "Open the workbench" (`#/workbench`). Right: a framed live mini version of the CS-S1 plan table (6 to 8 rows, role tags, actions). Under the hero, a row of three proof metrics, all read from data with a source caption: CS-S1 composite ours vs B2-k (leaderboard), free-text identifier leakage ours vs B2-k (scorecard risk components), and the CS-S1 gate result.
2. **The problem.** Two columns: "What the analytics vendor needs" (intent, handle time, conversation text) and "What comes along by default" (names, ID numbers read aloud, spelled emails, health remarks, the customer table). Below, three short facts with sources: B2-k text leakage; the c20 finding ("a column presented as pseudonymised was the national ID, hashed, and is reversible"); the baseline's not-answerable intent-model task.
3. **How it works.** A linear row of four stages, Detect, Plan, Transform, Verify, each with a one-line caption and a small status label. Beside it, one sticky product frame whose content swaps as each stage enters view: detection labels with reasons; the plan table; original vs protected turn with span tags (reuse SpanTag); the gate checks and pass state.
4. **Use cases: one dataset, two purposes.** CS-S1 (external analytics vendor) and CS-S3 side by side, using each scenario's real title and recipient from the data (CS-S3 is quality-audit samples to an outsourced partner; its tasks need only aggregates, so transcripts are withheld). For each: tables released, tables withheld, the rows whose action differs highlighted in `--pf-accent-tint`, and one composite score. A small text link: "A third purpose, CS-S2, is in the workbench."
5. **Evidence.** Grouped bar chart (reuse the Carbon chart, recoloured: PurposeFit teal, baselines greys) for CS-S1: B0, B2, B2-k, PurposeFit on privacy, utility, composite. A compact table: detection held-out macro-F1 rules-only and with LLM vs B1; health leakage before and after (if present in the data, otherwise hide the row); AI-off parity (final-CS-S1-nollm vs final-CS-S1). Every number has a source caption (tool, split, run id).
6. **Trust and transparency.** Three cards: a policy card excerpt with the EDPB terms (pseudonymisation secret: key id only; pseudonymisation domain: the named recipient; additional information: held by the controller); the verification checks with pass or fail; known limitations from the residual-risk list. Below, a quiet strip of safeguards: "AI sees masked text only", "Separate keys per recipient", "Export blocked unless the gate passes", "Every README number checked by make verify-claims".
7. **Final call to action.** One Serif line, "See your own release plan.", the "Open the workbench" button, a GitHub link, and the credit "Built for the TrustED PETs Transformer challenge, Since AI Hackathon 2026". No newsletter, no form.

## Motion

- Sticky stacking: each panel `position: sticky; top: 0` with rising `z-index` (exists).
- Covered panel: one `requestAnimationFrame` loop driven by Lenis's scroll event computes each panel's covered progress p (0 to 1) and sets `--p`. The covered panel uses `transform: scale(calc(1 - 0.04 * var(--p)))` and `opacity: calc(1 - 0.35 * var(--p))`. Animate only transform and opacity.
- Scroll progress: a 2 px `--pf-accent` bar fixed at the top, width from the same scroll value.
- Hover: product frames lift 2 px and the shadow deepens slightly over 150 ms. Nothing else moves on hover.
- Below 768 px and with `prefers-reduced-motion`: no sticky stacking, no scaling, no Lenis; content appears without animation.
- All motion values as CSS variables at the top of `landing.scss`.

## Product visuals

Live components fed by the same data the workbench uses, inside a framed "app window" (surface, 1 px line, radius, shadow, a thin title bar with the run id in Plex Mono). Never images of numbers. Never invented data.

## Never

Customer logos, testimonials, certifications or compliance badges for PurposeFit, "secure", "anonymous", "compliant", "guaranteed", em dashes, hard-coded numbers.

## Done when

- `npm run build` passes; `npm audit --omit=dev` has no high or critical findings.
- Works at 1440, 1280 and 390 px; keyboard reachable; visible focus; text contrast AA.
- Commit on branch `ui`, push, and report: what was built per section, anything left out, and how to tune the motion.
