"""Feasibility spike (research evidence only, not product code).

Question: how much of the B2 free-text leakage (~80 %) can a controller-side hybrid redactor remove,
using only (a) regex + validators, (b) spoken/spelled-number and e-mail normalisation, and
(c) a name gazetteer built from the controller's OWN structured columns (customers.full_name,
conversations.agent_name) - no gold labels, no adversary files.
Run on the customer_service TRAIN split; score with pets_eval.text.
"""
import json, re, sys
from pathlib import Path
import pandas as pd
from pets_eval import text as T

ROOT = Path(sys.argv[1])
D = ROOT / "data" / "customer_service"
turns = pd.read_csv(D / "turns.csv", dtype=str, keep_default_na=False)
conv = pd.read_csv(D / "conversations.csv", dtype=str, keep_default_na=False)
cust = pd.read_csv(D / "customers.csv", dtype=str, keep_default_na=False)
train_ids = set(conv[conv.split == "train"].conversation_id)
turns = turns[turns.conversation_id.isin(train_ids)]

# ---- gazetteer from the controller's own structured data --------------------------------
names = set()
for full in list(cust.full_name) + list(conv.agent_name):
    for tok in re.split(r"[\s\-]+", full.lower()):
        if len(tok) >= 3:
            names.add(tok)
STOP = {"aino", "toivo", "onni", "lumi", "satu", "usko", "tuuli", "ilma", "sini", "mari", "aalto"}  # tiny, editable
names -= {"the", "and", "och", "det", "jag", "hej"}
word_re = re.compile(r"[A-Za-zÅÄÖåäöÉéÜü]+")

DIG = {  # fi / en / sv digit words
    "nolla": 0, "yksi": 1, "kaksi": 2, "kolme": 3, "neljä": 4, "viisi": 5, "kuusi": 6, "seitsemän": 7, "kahdeksan": 8, "yhdeksän": 9,
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "noll": 0, "ett": 1, "en": 1, "två": 2, "tre": 3, "fyra": 4, "fem": 5, "sex": 6, "sju": 7, "åtta": 8, "nio": 9,
}
dw = "|".join(sorted(DIG, key=len, reverse=True))
spoken_re = re.compile(rf"\b(?:(?:{dw}|\d+|[a-z])\b[\s,\-]*){{4,}}", re.I)  # >=4 digit-ish tokens

PATTERNS = [
    ("NATIONAL_ID", r"\b\d{6}[-+A-FYXWVU]\d{3}[0-9A-Y]\b"),
    ("IBAN", r"\b[A-Z]{2}\d{2}(?:\s?[0-9A-Z]{4}){3,7}(?:\s?[0-9A-Z]{1,4})?\b"),
    ("PAYMENT_CARD", r"\b(?:\d[ -]?){13,19}\b"),
    ("EMAIL", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    ("EMAIL", r"\b[\w]+(?:\s(?:dot|piste|punkt)\s[\w]+)*\s(?:at|ät|snabel-a|miukumauku)\s[\w]+(?:\s(?:dot|piste|punkt)\s[\w]+)+"),
    ("URL", r"https?://\S+"),
    ("IP_ADDRESS", r"\b(?!192\.168\.1\.1\b)(?:\d{1,3}\.){3}\d{1,3}\b"),
    ("PHONE", r"(?:\+358|\b0)\s?\d{1,3}[\s-]?\d{2,4}[\s-]?\d{2,4}(?:[\s-]?\d{1,4})?\b"),
    ("DEVICE_ID", r"\b\d{15}\b|\b89\d{17,19}\b"),
    ("PROPERTY_ID", r"\b\d{3}-\d{1,3}-\d{1,4}-\d{1,4}\b"),
    ("LICENSE_PLATE", r"\b[A-ZÅÄÖ]{2,3}-\d{1,3}\b"),
    ("ACCOUNT_NUMBER", r"\b\d{6,10}\b"),
    ("ADDRESS", r"\b[A-ZÅÄÖ][a-zåäö]+(?:katu|tie|kuja|polku|rinne|mäki|ranta|gatan|vägen|gränd|road|street)\s\d+(?:\s?[A-Z]\s?\d*)?(?:,\s?\d{5}\s[A-ZÅÄÖ][a-zåäö]+)?"),
    ("SECRET", r"(?i)(?:salasana|password|lösenord|pin|puk)(?:\s(?:on|is|är|koodi|code))?[\s:]+(\S+)"),
]
PATTERNS = [(l, re.compile(p)) for l, p in PATTERNS]


def detect(t: str):
    spans = []
    for lab, rx in PATTERNS:
        for m in rx.finditer(t):
            s, e = (m.start(1), m.end(1)) if rx.groups else (m.start(), m.end())
            spans.append({"start": s, "end": e, "label": lab})
    for m in spoken_re.finditer(t):
        toks = re.findall(r"\w+", m.group(0).lower())
        if sum(tok in DIG or tok.isdigit() for tok in toks) >= 4:
            spans.append({"start": m.start(), "end": m.end(), "label": "NATIONAL_ID"})
    for m in word_re.finditer(t):
        if m.group(0).lower() in names: spans.append({"start": m.start(), "end": m.end(), "label": "PERSON"})
    spans.sort(key=lambda s: (s["start"], -(s["end"] - s["start"])))
    out, last = [], -1
    for s in spans:  # drop overlaps, keep the earliest/longest
        if s["start"] >= last:
            out.append(s); last = s["end"]
    return out


gold = {}
tid = set(turns.turn_id)
for line in open(ROOT / "metadata/pii_spans/customer_service__turns__text.jsonl"):
    r = json.loads(line)
    if r["record_id"] in tid:
        gold[r["record_id"]] = r["spans"]
texts = dict(zip(turns.turn_id, turns.text))
pred = {rid: detect(t) for rid, t in texts.items()}
red = {}
for rid, t in texts.items():
    out, pos = [], 0
    for s in pred[rid]:
        out.append(t[pos:s["start"]]); out.append(f"[{s['label']}]"); pos = s["end"]
    red[rid] = "".join(out) + t[pos:]

sc = T.span_scores(gold, pred, mode="overlap", label_agnostic=True)
print("label-agnostic overlap:", sc["micro"])
lk = T.redaction_leakage(gold, red)
print("leakage summary:", {k: v for k, v in lk.items() if k != "per_label" and k != "examples"})
for lab, v in sorted(lk.get("per_label", {}).items()):
    print(f"  {lab:15s} n={v['n']:6d} leak={v['rate']:.2f}")
