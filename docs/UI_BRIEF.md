# PurposeFit UI brief (for the front-end agent)

You build only the web front end, inside `web/`, on branch `ui`. Another agent builds the Python pipeline and the API on `main` at the same time. You never edit anything outside `web/`. Read this file, then `PROJECT_BRIEF.md`, `docs/API_CONTRACT.md`, `docs/FACTS.md` and `CLAUDE.md`.

## 1. What the product is, in one paragraph

PurposeFit prepares a dataset for one named recipient and purpose. It detects what each column holds, decides per column what to release and how (keep, drop, keyed pseudonym, generalise, redact, withhold the table), removes identifiers from free text, then re-runs the organisers' privacy attacks and utility checks before it allows export. The user is a data steward or privacy officer who must justify the release to someone else. The UI exists to make each decision visible, explained and backed by a measured number.

## 2. The demo story the UI must carry (4 minutes)

1. Pick dataset `customer_service` and scenario CS-S1: an external analytics vendor that mines contact reasons from support conversations.
2. Plan screen: every field with its detected role, the action taken and a one-line reason. The `customers` table is withheld because no task needs it.
3. Switch the scenario to CS-S3 (aggregate volumes only). The plan visibly changes: the transcripts are withheld too. This "same data, two recipients, two plans" moment is the core idea of the product. Make the switch one click and make the differences easy to see.
4. Text screen: an original transcript turn next to its protected version. Each removed span is labelled with its type and the layer that caught it.
5. Verify screen: the release gate result, our scores next to the B2-k baseline, the utility tasks, and the residual risks we disclose.
6. Export screen: download the release and the policy card.

## 3. Design decisions already made (do not reopen)

- **Design system: IBM Carbon, used as shipped.** `@carbon/react`, `@carbon/charts-react`, `@carbon/icons-react`, Apache 2.0. Theme `g10` for content, the UI Shell header in `g100` (dark), as in Carbon's own examples. Font: IBM Plex Sans and Plex Mono through Carbon's styles only.
- **Square corners.** Carbon uses a zero radius on tiles, tables, inputs and buttons. Do not add border radius anywhere. Rounded cards everywhere are the default look of AI-generated apps and we want the opposite: a serious data tool. The only rounded element allowed is Carbon's own pill-shaped `Tag`, used for roles and risk labels.
- **No AI look:** no gradients, no glow, no sparkle or magic-wand icons, no emoji, no glassmorphism, no oversized hero text, no illustrations.
- **Concept screens** drawn earlier used rounded cards and a teal palette. Treat them as layout reference only. Carbon's look wins.

## 4. Copy rules

- Sentence case for every label, heading and button.
- No em dashes and no decorative dashes. Use a full stop or a colon.
- Every number shows its unit and where it came from, for example "7.6 % leakage · pets-eval · train split".
- Only state facts in `docs/FACTS.md`. Never write "anonymous", "anonymised", "GDPR compliant", "secure" or "guaranteed".
- Name techniques by their real names: "keyed pseudonym (HMAC-SHA256)", "generalised to hour", "k-anonymity, k = 5", "withheld: not needed for this purpose".
- Short, plain sentences. No marketing tone.

## 5. Screens

Use the Carbon UI Shell: `Header` with the product name "PurposeFit" and the current dataset and scenario, a `SideNav` or a `ProgressIndicator` for the five steps (Scenario, Plan, Text, Verify, Export).

### 5.1 Scenario
- `Dropdown` for dataset. Only `customer_service` is required; show others as disabled with "not in this demo".
- Selectable `Tile`s for scenarios, each showing recipient, purpose and the utility tasks it needs (from the scenario fixture).
- A "Compare plans" action that opens the Plan screen with two scenarios side by side.

### 5.2 Plan
- `DataTable` with toolbar search. Columns: table, column, detected role (`Tag`), subtype, action, level (for generalised fields), reason. Group or sort by table.
- Withheld tables shown as their own rows or an `InlineNotification` "Withheld: not needed for this purpose".
- Compare mode: two plans side by side, with rows whose action differs highlighted using Carbon's own selected or highlighted row style, not custom colours.
- A small panel for detection findings, for example "Column c20 is an unkeyed SHA-256 of the national ID in c05. Reversible by enumeration." Show the finding text from the fixture; do not invent findings.

### 5.3 Text
- Two `Layer` panels: original turn, protected turn.
- Removed spans shown as Carbon `Tag` or `CodeSnippet` inline with their label (`PERSON`, `NATIONAL_ID`, ...) and a small caption with the layer that caught it (patterns, normalise, gazetteer, cues, ner, health).
- A `Toggle` for typed placeholders or consistent surrogates (if the fixture has both; otherwise disabled with "available after Phase 5").
- Pagination through example turns.
- A per-label leakage summary (bar chart or table) when the fixture provides it.

### 5.4 Verify
- Gate result as an `InlineNotification`: success "Release gate passed for CS-S1" or error naming the failing check. Use the gate object from the fixture.
- Headline `Tile`s: privacy, utility, composite for ours, each with the B2-k value underneath, same scenario, same scorer.
- `@carbon/charts-react` grouped bar chart: privacy, utility, composite, ours vs B2-k.
- Utility task table: task id, description, ours, B2-k. Show "not answerable" as text, never as 0.
- Risk components table: component, ours, B2-k.
- pyCANON k next to the pipeline's k when present.
- Residual risks as a plain list, from the fixture.
- An ablation table (layer switched off, leakage, utility) when the fixture provides it; hide the section otherwise.

### 5.5 Export
- Buttons: download release (zip), download policy card (JSON or Markdown).
- A note: "Row maps and keys stay with the data controller and are never exported."

## 6. Current numbers (from runs/leaderboard.csv, for fixtures only, never hard-coded)

| Scenario | Method | Privacy | Utility | Composite |
|---|---|---|---|---|
| CS-S1 | PurposeFit, Phase 4 (text not yet redacted) | 0.375 | 1.000 | 0.524 |
| CS-S1 | B2-k | 0.495 | 0.748 | 0.585 |
| CS-S3 | PurposeFit, Phase 4 | 1.000 | 1.000 | 1.000 |
| CS-S3 | B2-k | 0.495 | 1.000 | 0.643 |

CS-S1 privacy will rise after the text redactor lands. The UI must read numbers from data, so it updates without code changes.

## 7. Data

- `web/src/api.ts` is the only place that fetches data. With `VITE_USE_FIXTURES=true` it reads `web/fixtures/*.json`; otherwise it calls the API exactly as `docs/API_CONTRACT.md` describes.
- Write TypeScript types for every response shape in `web/src/types.ts`, matching the contract. If the contract and the fixtures disagree, follow the fixtures and list the gap in your report.
- Fixture text is synthetic. Never log fixture contents to the console.

## 8. Quality bar

- Keyboard-only navigation works on every screen; visible focus; `aria-label` on icon-only buttons.
- Text contrast passes WCAG AA (Carbon's tokens already do if you do not override colours).
- Works at 1280 px and stays usable at 390 px (tables scroll inside their container).
- `npm run build` passes with no TypeScript errors; `npm audit --omit=dev` has no high or critical findings.
- No new dependencies beyond Vite, React, TypeScript, the Carbon packages and `sass`, unless you explain why.

## 9. Git rules

- Work only in `web/` on branch `ui`. Commit in small steps with clear messages. Push the branch.
- Never commit `.env`, keys, `node_modules/` or `web/dist/`.
- Do not merge into `main`. The other agent merges in Phase 9.

## 10. Your final report

What you built per screen, how to run it (`npm install`, `VITE_USE_FIXTURES=true npm run dev`), build and audit output, any contract gaps, and three screenshots described in words (Plan compare mode, Text, Verify).
