"""Download the latest DVV first-name and surname lists into data/gazetteer/.

Source: Digi- ja vaestotietovirasto (DVV), "Vaestotietojarjestelman suomalaisten nimiaineistot",
https://www.avoindata.fi/data/en/dataset/none , licence CC BY 4.0.

Writes the two XLSX files plus data/gazetteer/SOURCES.json (url, date, size, sha256).
The XLSX files are git-ignored; rerun this script to rebuild them.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

API = "https://www.avoindata.fi/data/api/3/action/package_show?id=none"
OUT = Path(__file__).resolve().parents[1] / "data" / "gazetteer"
WANTED = {"etunimitilasto": "first_names", "sukunimitilasto": "surnames"}


def _get(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("only https sources are allowed")
    req = urllib.request.Request(url, headers={"User-Agent": "purposefit-gazetteer-fetch"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310 (https checked above)
        return resp.read()


def main() -> None:
    pkg = json.loads(_get(API))["result"]
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        "dataset": pkg["title"],
        "publisher": "DVV",
        "licence": pkg["license_title"],
        "page": "https://www.avoindata.fi/data/en/dataset/none",
        "files": [],
    }
    for prefix, kind in WANTED.items():
        cands = [
            r
            for r in pkg["resources"]
            if r.get("format", "").upper() == "XLSX" and r["url"].split("/")[-1].startswith(prefix)
        ]
        if not cands:
            raise SystemExit(f"no XLSX resource found for {kind}")
        res = max(cands, key=lambda r: r.get("last_modified") or r.get("created") or "")
        data = _get(res["url"])
        name = res["url"].split("/")[-1]
        (OUT / name).write_bytes(data)
        sources["files"].append(
            {
                "kind": kind,
                "file": name,
                "url": res["url"],
                "modified": res.get("last_modified") or res.get("created"),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        print(f"{kind}: {name} {len(data)} bytes")
    (OUT / "SOURCES.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
