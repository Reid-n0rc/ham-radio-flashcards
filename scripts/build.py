#!/usr/bin/env python3
"""Build flash card PDFs for every pool in pools/index.json into cards/."""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_cards import build  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOLS, CARDS = os.path.join(ROOT, "pools"), os.path.join(ROOT, "cards")


def fingerprint(pool_dir, excl):
    h = hashlib.sha256()
    h.update(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_cards.py"), "rb").read())
    pool = [q for q in json.load(open(os.path.join(pool_dir, "pool.json"))) if q["id"] not in set(excl)]
    h.update(json.dumps(pool, sort_keys=True).encode())
    for fig in sorted({q["figure"] for q in pool if q.get("figure")}):
        h.update(open(os.path.join(pool_dir, fig), "rb").read())
    return h.hexdigest()


def main():
    os.makedirs(CARDS, exist_ok=True)
    index = json.load(open(os.path.join(POOLS, "index.json")))
    wpath = os.path.join(ROOT, "ncvec", "withdrawn.json")
    withdrawn = json.load(open(wpath)) if os.path.exists(wpath) else {}
    rows, made, manifest = [], set(), []
    mpath = os.path.join(CARDS, "manifest.json")
    prev = {m["name"]: m for m in json.load(open(mpath))} if os.path.exists(mpath) else {}
    for p in index:
        name, cls = p["name"], p["class"]
        years = name.split("-", 1)[1]
        fn = f"{cls.replace(' ', '_')}_{years}_Flash_Cards.pdf"
        pool_ids = {q["id"] for q in json.load(open(os.path.join(POOLS, name, "pool.json")))}
        excl = sorted(set(withdrawn.get(name, [])) & pool_ids)
        fp = fingerprint(os.path.join(POOLS, name), excl)
        old = prev.get(name)
        if old and old.get("fingerprint") == fp and old["pdf"] == fn and os.path.exists(os.path.join(CARDS, fn)):
            nq, nf, sheets = old["questions"], old["figure_cards"], old["sheets"]
            print(f"{fn}: unchanged")
        else:
            nq, nf, sheets = build(os.path.join(POOLS, name), os.path.join(CARDS, fn),
                                   f"{cls} {years} Question Pool Flash Cards", excl)
        made.add(fn)
        manifest.append(dict(p, questions=nq, pdf=fn, figure_cards=nf, sheets=sheets, cards=nq + nf,
                             excluded=excl, bytes=os.path.getsize(os.path.join(CARDS, fn)),
                             fingerprint=fp))
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
