# PurposeFit

PurposeFit compiles a data release for one stated purpose. It asks three questions: who receives the data, for what purpose, and who might attack it. It then keeps only what the purpose needs, gives join keys keyed pseudonyms (HMAC-SHA256), coarsens quasi-identifiers until k-anonymity holds, removes identifiers from free text, and re-runs the proving ground's attacks before anything can be exported.

Built for the Since AI Hackathon 2026, TrustED PETs Transformer challenge, on the synthetic TrustED proving ground only.

Status: phase 0 (repo setup). See `docs/ARCHITECTURE.md` for the design and `docs/BUILD_GUIDE.md` for the phases.

## Run locally

Requires [uv](https://docs.astral.sh/uv/). Python 3.11 is pinned in `.python-version`.

```bash
uv sync
cp .env.example .env        # then fill in the values
uv run python scripts/fetch_gazetteer.py
```

The proving ground is not in this repo. Unzip it into `vendor/proving_ground/`.

## Limitations

- Pseudonymised data is still personal data (GDPR Recital 26).
- k-anonymity limits singling out on the stated quasi-identifiers only; it does not stop attribute inference inside a uniform group.

## Licences and attribution

- Finnish first-name and surname lists: Digi- ja väestötietovirasto (DVV), "Väestötietojärjestelmän suomalaisten nimiaineistot", https://www.avoindata.fi/data/en/dataset/none , licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Downloaded by `scripts/fetch_gazetteer.py`; file names, dates and checksums are in `data/gazetteer/SOURCES.json`. We use the lists unmodified as a lookup source.
- TrustED proving ground: see its own `LICENSE` and `LICENSE-DATA.md`; not redistributed here.
