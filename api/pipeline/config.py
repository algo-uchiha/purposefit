"""Tunable thresholds in one place. Values follow docs/ARCHITECTURE.md (release gate)."""

# Release gate (docs/ARCHITECTURE.md, "Release gate").
GATE_MAX_DIRECT_IDENTIFIERS = 0.0  # residual direct identifiers in structured columns
GATE_MIN_K = 5  # k-anonymity confirmed by pyCANON on the released quasi-identifiers
GATE_MAX_TEXT_LEAKAGE = 0.10  # identifying leakage in free text, pets-eval rate

# Keyed pseudonyms: lowercase hex length after the column prefix.
PSEUDONYM_HEX = 20
