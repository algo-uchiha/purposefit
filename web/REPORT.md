# PurposeFit web implementation report

## Screens built

- **Scenario:** Carbon dataset selector, disabled datasets labelled “not in this demo”, and scenario tiles populated from the scenario fixture. CS-S1 and CS-S3 can be switched directly to show how the same dataset yields different plans.
- **Plan:** Searchable field policy table with role tags, action, level and fixture reason. Compare mode joins policies from both scenarios and marks changed actions. The findings panel uses finding fixture data.
- **Text:** Original and protected synthetic turns, paging, span labels and layer names, a surrogate toggle enabled only when surrogate data exists, and per-label leakage results when supplied. CS-S3 displays the withheld notice.
- **Verify:** Gate verdict and blocking reasons read from the gate object, score tiles and grouped chart using scorecard data, utility and risk tables, k values from pipeline and pyCANON, residual risks, and conditional ablation results. Threshold values are displayed from each gate check; no threshold or verdict is embedded in UI logic.
- **Export:** Release download is disabled unless the fixture/API gate passes. Policy card download appears when `policy_card` is present. Includes the required row map and key note.

## Run

From `web/`:

```sh
npm install
VITE_USE_FIXTURES=true npm run dev
```

Fixture requests read `web/fixtures/*.json`. API mode uses the paths from `docs/API_CONTRACT.md` in `src/api.ts`.

## Build and audit

- `npm run build`: **passed**. TypeScript and Vite completed; Vite emitted a bundle-size advisory for the 974.17 kB JavaScript chunk.
- `npm audit --omit=dev --offline`: **passed**, 0 vulnerabilities in the locally available advisory data. The online audit endpoint could not resolve `registry.npmjs.org`, so its advisory database could not be refreshed.

## Contract gaps

No direct shape disagreement was found in the inspected fixture files. The API contract does not define a `GET /api/findings` endpoint, though findings are a property of the detect stage. The current API-mode findings loader calls `/findings`; a live implementation should instead read `findings` from `/runs/{id}/stages/detect`. Fixture mode loads the dedicated `findings.json` sample as required to build the panel. The release and policy card are not directly downloadable from fixtures, so those controls are presented as unavailable when fixture data lacks a policy card, and the API export route is wired for live mode.

## Screenshots described

- **Plan compare mode:** A searchable table joins each field in CS-S1 and CS-S3, with the action differences shown in a selected-row tint and both scenario reasons listed in each row. A side panel shows released tables and detection findings.
- **Text:** Two square Carbon tiles place the selected original synthetic turn beside its protected version. Any spans carry a type tag and layer caption; paging and the conditional surrogate switch sit above the comparison.
- **Verify:** The gate notification leads the screen, followed by three score tiles, a grouped PurposeFit/B2-k chart, gate checks, utility tasks, risk components, k results, and residual risks. The threshold and observed values come from the selected scenario fixture.
