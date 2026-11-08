# Landing and flow v3 brief (replaces LANDING_V2_BRIEF.md)

Design reference: Design canvas "PurposeFit landing, Vanta-style direction"
https://claude.ai/artifact/3DBBHcuhdA2sRr15DryJB4  (7 boards: Landing, Start, Found, Plan, Calls, Proof, Safe)
If you cannot open it, follow this file. Wording is placeholder where marked; real numbers come from FACTS.md and fixtures.

## Scope and rules
- Branch ui. First `git merge main`. Commit small and often; leave nothing uncommitted.
- Allowed to edit: web/src/landing/**, web/src/screens/**, web/src/components/**, web/src/styles/**. Do not change api.ts types, the API, or anything outside web/.
- No em dashes, no emoji, sentence case, no invented numbers, logos, testimonials or certifications.
- Every number shown must come from fixtures / the API (see Scale below) or FACTS.md. Mock-up values like 0.98, 0.58, 0.34 are the CS-S1 combined scores: PurposeFit 0.9842, best baseline B2-k 0.5849, B0 0.3438. Read them from runs/leaderboard fixtures, do not hardcode.
- Real buttons and links, labels on icon buttons, text contrast 4.5:1, respect prefers-reduced-motion.
- "Try the demo" goes to #/workbench (the Start screen). There is no upload in this build: say so on Start.

## Tokens
Ink #0B1F2A, text #3C4D57, muted #5B6B74, accent teal #0E7C7B, tint #EAF5F4, mint #DDF1EF, border #E1EAEC, pass #1F7A4D on #E3F3EA, risk #9C2A1E on #FDE7E4, amber #7A5200 on #FFF3D6, info #254A8F on #E6EEFB.
Font Inter 400/500/600. Radius: cards 16 to 20, buttons and chips 999 (pills). Headings tight: letter-spacing -0.035em, line-height ~1.05.
Logo: two overlapping circles (ink and teal at 0.9 opacity, 32x24) plus the word PurposeFit, weight 600.
Background: soft blurred blobs, no library. Absolutely positioned circles, filter blur(90px), colors #CDE8F6 (blue), #D5F0E9 (mint), #E3DCF6 (lavender), #FCE9DA (peach, small, sparing), opacity 0.7 to 0.9, pointer-events none, 3 to 4 per screen, different positions per screen. Panels alternate #F4FAFC and #FFFFFF.

## Landing: 5 full-screen panels
Each panel is exactly 100vh (min 700px), one idea, content vertically centered, scroll-snap-type y mandatory with scroll-snap-align start. Everything of a panel must fit without inner scrolling at 1440x900 and 1280x720; scale type with clamp() for smaller heights. Keep the Lenis smooth scroll only if it does not fight snapping; otherwise drop it. Fixed nav (logo, links, "Try the demo" pill) over panel 1 and following panels.
1. Score. Pill "PurposeFit, built for the TrustED PETs challenge". H1 "Same data. Far safer. Still useful." One-line sub. Three columns bar chart: Shared as it is, Best standard approach, PurposeFit (value above each bar, PurposeFit bar teal and larger number). Bars animate up on load. Two buttons: Try the demo, See what changes.
2. What changes. H2 "One record in. A safe copy for each person out." Left: original record with sensitive spans highlighted red. Arrow. Right: two cards, "Copy for the analytics team" and "Copy for an outside vendor", changed spans highlighted mint. Use one real example row from fixtures if it exists, else the made-up Maija Virtanen example marked as made up.
3. How it works. H2 "Four steps. You see every one." Four cards with line icons: Find what is sensitive, Decide by purpose, Protect it, Prove it is safe.
4. Safety. H2 "Nothing leaves until the checks pass." Four stat cards from fixtures: direct identifiers left 0, smallest group 5+, identifying details left in call text 0.9% (train), health details left 0% down from 95.6% (train). One honest line: works on prepared files, live database connections and user accounts are not built.
5. Demo. H2 "Try it on a real example in under a minute." Three small preview cards (Your data, Choose protection, Check the proof) linking to the workbench, big Try the demo button, footer line inside the panel.
Recipient names in copy (analytics team, outside vendor, research partner) must match scenarios.json labels. Use the same labels in the UI.

## Workbench flow (restyle to the same look; keep real data and the server-side gate)
Shell: left sidebar (logo, 4 steps: Your data, Choose protection, Check the proof, Download; done steps teal dot, current step tinted), blob background, content on the right. Screens, in order:
1. Start (Your data): dataset card "Customer service calls" with Loaded pill, REAL counts, and a table WINDOW of real rows with page controls. Footer note: "Uploading your own file is not built yet. This demo uses prepared example data." Button "Find what is sensitive".
2. Found: same table window, column headers carry chips: Identifies a person (red), Could identify in a mix (amber), Safe on its own (green), Free text (blue). Summary tiles with counts per class from the detection output. Button "Choose who the copy is for".
3. Plan (Choose protection): segmented control of recipients from scenarios.json. Rows: field, what it is, what we do (Replace with a code, Group into ranges, Remove, Black out sensitive words, Keep as is), why. Right card: before and after preview. Button "Protect this copy".
4. Calls (text): original vs safe copy of a real transcript from fixtures, spans labelled NAME, ID NUMBER, HEALTH DETAIL (use the redactor's real labels), legend, real leakage numbers.
5. Proof: three check cards (direct identifiers, group size k, text leakage) with Pass or Fail, score bars vs baselines, "Read the report" (policy card), Download enabled only when the API gate says pass.
6. Safe (Download): Before table and After table side by side (windows), All checks passed pill, Read the report, Download safe copy.
Plain words only on screen. Technical terms (k-anonymity, HMAC, pseudonymisation) live in the report, not the main UI.

## Scale: the real data is large
Never imply the sample rows are the whole dataset. Rules:
- Show real counts at the top of Start and Safe (conversations, turns, columns). Format with thousands separators.
- Every table is a window: caption "Showing 25 of 11,943", page controls, and a column filter or search. Server-side paging if the API supports it, otherwise page the exported fixture. Never render all rows. Virtualise or cap at 50 rows per page.
- Add a "Changed in this copy" summary under the Safe tables from real counts: values replaced, values grouped, values removed, spans hidden in text.
- Keep fixtures small (export_ui_fixtures.py already samples); the UI must work the same when VITE_USE_FIXTURES=false.

## Priority order (time is short, code freeze 06:30)
1. Landing panels 1 to 5 (must). 2. Shell + Start + Safe screens. 3. Found, Plan, Proof. 4. Calls. Commit after each. Then run `npm run build` and `npm audit --omit=dev` and report: files changed, fixtures vs real API, anything you could not do.
