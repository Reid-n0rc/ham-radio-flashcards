#!/usr/bin/env python3
"""Copy the current (and any already-released upcoming) question pools from a
checkout of the upstream machine-readable pool repo into pools/.

A pool named <class>-<Y1>-<Y2> is in effect July 1 of Y1 through June 30 of Y2.
Expired pools are removed. Writes pools/index.json.
"""
import datetime as dt
import json
import os
import re
import shutil
import sys

CLASSES = {"technician": "Technician", "general": "General", "extra": "Amateur Extra"}
NAME_RE = re.compile(r"^(technician|general|extra)-(\d{4})-(\d{4})$")


def status(start, end, today):
    if today < dt.date(start, 7, 1):
        return "upcoming"
    if today <= dt.date(end, 6, 30):
        return "current"
    return "expired"


def validate(name, pool, src):
    ids = [q["id"] for q in pool]
    assert len(ids) == len(set(ids)), f"{name}: duplicate IDs"
    assert len(pool) >= 300, f"{name}: only {len(pool)} questions"
    prefix = {"technician": "T", "general": "G", "extra": "E"}[name.split("-")[0]]
    for q in pool:
        assert q["id"].startswith(prefix), f"{name}: bad id {q['id']}"
        assert len(q["answers"]) == 4 and all(a.strip() for a in q["answers"]), f"{q['id']}: answers"
        assert q["correct_letter"] in "ABCD", f"{q['id']}: letter"
        assert "ABCD"[q["correct"]] == q["correct_letter"], f"{q['id']}: letter/index mismatch"
        assert q["question"].strip(), f"{q['id']}: empty question"
        if q.get("figure"):
            assert os.path.exists(os.path.join(src, q["figure"])), f"{q['id']}: missing {q['figure']}"


def main(upstream, dest, today=None):
    today = today or dt.date.today()
    os.makedirs(dest, exist_ok=True)
    index = []
    for d in sorted(os.listdir(upstream)):
        m = NAME_RE.match(d)
        if not m:
            continue
        cls, y1, y2 = m.group(1), int(m.group(2)), int(m.group(3))
        st = status(y1, y2, today)
        if st == "expired":
            continue
        src = os.path.join(upstream, d)
        js = os.path.join(src, f"{d}.json")
        if not os.path.exists(js):
            continue
        pool = json.load(open(js))
        validate(d, pool, src)
        out = os.path.join(dest, d)
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        with open(os.path.join(out, "pool.json"), "w") as f:
            json.dump(pool, f, indent=1, ensure_ascii=False)
            f.write("\n")
        for fig in sorted({q["figure"] for q in pool if q.get("figure")}):
            shutil.copy2(os.path.join(src, fig), out)
        index.append({"name": d, "class": CLASSES[cls], "start": f"{y1}-07-01",
                      "end": f"{y2}-06-30", "status": st, "questions": len(pool)})
    keep = {p["name"] for p in index}
    for d in os.listdir(dest):
        if os.path.isdir(os.path.join(dest, d)) and d not in keep:
            shutil.rmtree(os.path.join(dest, d))
    with open(os.path.join(dest, "index.json"), "w") as f:
        json.dump(index, f, indent=1)
        f.write("\n")
    for p in index:
        print(f"{p['name']}: {p['status']}, {p['questions']} questions")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
