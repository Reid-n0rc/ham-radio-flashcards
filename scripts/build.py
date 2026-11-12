#!/usr/bin/env python3
"""Build flash card PDFs for every pool in pools/index.json into cards/."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_cards import build  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOLS, CARDS = os.path.join(ROOT, "pools"), os.path.join(ROOT, "cards")


def main():
    os.makedirs(CARDS, exist_ok=True)
    index = json.load(open(os.path.join(POOLS, "index.json")))
    wpath = os.path.join(ROOT, "ncvec", "withdrawn.json")
    withdrawn = json.load(open(wpath)) if os.path.exists(wpath) else {}
    rows, made, manifest = [], set(), []
    for p in index:
        name, cls = p["name"], p["class"]
        years = name.split("-", 1)[1]
        fn = f"{cls.replace(' ', '_')}_{years}_Flash_Cards.pdf"
        pool_ids = {q["id"] for q in json.load(open(os.path.join(POOLS, name, "pool.json")))}
        excl = sorted(set(withdrawn.get(name, [])) & pool_ids)
        nq, nf, sheets = build(os.path.join(POOLS, name), os.path.join(CARDS, fn),
                               f"{cls} {years} Question Pool Flash Cards", excl)
        made.add(fn)
        manifest.append(dict(p, pdf=fn, figure_cards=nf, sheets=sheets, cards=nq + nf,
                             excluded=excl, bytes=os.path.getsize(os.path.join(CARDS, fn))))
        note = f"excluded per NCVEC: {', '.join(excl)}" if excl else ""
        rows.append(f"| [{fn}]({fn}) | {cls} | {p['start']} to {p['end']} | {p['status']} "
                    f"| {nq} | {nf} | {sheets} | {note} |")
        print(f"{fn}: {nq} questions, {nf} figure cards, {sheets} sheets {note}")
    for f in os.listdir(CARDS):
        if f.endswith(".pdf") and f not in made:
            os.remove(os.path.join(CARDS, f))
    with open(os.path.join(CARDS, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1); f.write("\n")
    with open(os.path.join(CARDS, "README.md"), "w") as f:
        f.write("# Flash cards\n\nGenerated automatically. Do not edit.\n\n"
                "| File | Class | Valid | Status | Questions | Figure cards | Sheets | Notes |\n"
                "|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
