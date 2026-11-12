#!/usr/bin/env python3
"""Assemble the GitHub Pages site into _site/ from site/, cards/ and pools/."""
import datetime as dt
import json
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("SITE_OUT", os.path.join(ROOT, "_site"))


def git(*args):
    try:
        return subprocess.check_output(["git", "-C", ROOT, *args], text=True).strip()
    except Exception:
        return ""


def main():
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
    meta = {
        "pools": manifest,
        "updated": git("log", "-1", "--format=%cI", "--", "cards") or dt.datetime.utcnow().isoformat() + "Z",
        "built": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "repo": f"https://github.com/{repo}" if repo else "",
    }
    with open(os.path.join(OUT, "data", "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"site built: {len(manifest)} pools")


if __name__ == "__main__":
    main()
