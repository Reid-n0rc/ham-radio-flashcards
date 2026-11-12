#!/usr/bin/env python3
"""Assemble the GitHub Pages site into docs/ from site/, cards/ and pools/."""
import datetime as dt
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("SITE_OUT", os.path.join(ROOT, "docs"))


def main():
    mp = os.path.join(OUT, "data", "meta.json")
    prev_meta = json.load(open(mp)) if os.path.exists(mp) else {}
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "site"), OUT)
    os.makedirs(os.path.join(OUT, "data"))
    manifest = json.load(open(os.path.join(ROOT, "cards", "manifest.json")))
    for m in manifest:
        src = os.path.join(ROOT, "pools", m["name"])
        pool = [q for q in json.load(open(os.path.join(src, "pool.json")))
                if q["id"] not in set(m["excluded"])]
        figdir = os.path.join(OUT, "data", m["name"])
        os.makedirs(figdir)
        slim = []
        for q in pool:
            if q.get("figure"):
                shutil.copy2(os.path.join(src, q["figure"]), figdir)
            slim.append({"id": q["id"], "q": q["question"], "a": q["answers"],
                         "c": q["correct_letter"], "f": q.get("figure") or ""})
        with open(os.path.join(OUT, "data", m["name"] + ".json"), "w") as f:
            json.dump(slim, f, ensure_ascii=False, separators=(",", ":"))
    repo = os.environ.get("GITHUB_REPOSITORY", "Reid-n0rc/ham-radio-flashcards")
    prints = {m["name"]: m.get("fingerprint") for m in manifest}
    updated = prev_meta.get("updated") if prev_meta.get("prints") == prints else None
    meta = {
        "pools": manifest,
        "prints": prints,
        "updated": updated or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": f"https://github.com/{repo}",
    }
    with open(os.path.join(OUT, "data", "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"site built: {len(manifest)} pools")


if __name__ == "__main__":
    main()
