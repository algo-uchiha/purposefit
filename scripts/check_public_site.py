"""Guard for the static public site: fail if web/dist holds anything that must not be published.

Checks file types and a few content patterns only. It prints file names and counts, never file contents.
usage: python scripts/check_public_site.py web/dist
"""
import re
import sys
from pathlib import Path

FORBIDDEN_SUFFIX = {".csv", ".parquet", ".zip", ".env", ".pem", ".key", ".jsonl", ".sqlite", ".db"}
FORBIDDEN_NAME = re.compile(r"rowmap|row_map|\.env|pii_spans|field_catalog|truth", re.IGNORECASE)
SECRET_SHAPES = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9]{20,}|PURPOSEFIT_HMAC_KEY\s*=|GEMINI_API_KEY\s*=|BEGIN [A-Z ]*PRIVATE KEY")


def main(root: Path) -> int:
    bad: list[str] = []
    files = [p for p in root.rglob("*") if p.is_file()]
    for p in files:
        rel = p.relative_to(root)
        if p.suffix.lower() in FORBIDDEN_SUFFIX and p.name != ".nojekyll":
            bad.append(f"forbidden file type: {rel}")
        if p.name != ".nojekyll" and FORBIDDEN_NAME.search(p.name):
            bad.append(f"forbidden file name: {rel}")
        if p.suffix.lower() in {".json", ".js", ".html", ".css", ".md", ".txt", ".map"} and SECRET_SHAPES.search(p.read_text(errors="ignore")):
            bad.append(f"secret-like text in: {rel}")
    print(f"checked {len(files)} files under {root}")
    for b in bad:
        print("FOUND:", b)
    if not bad:
        print("clean")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
