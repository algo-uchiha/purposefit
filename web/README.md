# PurposeFit web

## Run the fixture demo

```sh
npm install
VITE_USE_FIXTURES=true npm run dev
```

Open the local URL printed by Vite. The demo starts on CS-S1. Use the scenario selector to switch to CS-S3 and see how purpose changes the release plan.

## Build and audit

```sh
npm run build
npm audit --omit=dev
```

The fixture mode loads JSON from `fixtures/`. API mode uses the endpoints in `docs/API_CONTRACT.md` through `src/api.ts`.

See [REPORT.md](REPORT.md) for the screen summary and verification results.
