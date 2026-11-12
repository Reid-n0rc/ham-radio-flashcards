#!/usr/bin/env python3
"""Watch NCVEC's question pool pages, the primary source for pool releases and errata.

- Discovers pool release pages from the ncvec.org menu.
- Fingerprints each page by its pool documents and its errata text.
- Extracts question IDs NCVEC lists as withdrawn/deleted and writes
  ncvec/withdrawn.json, which the build uses to drop those questions even if
  the upstream data has not caught up yet.
- Writes ncvec/state.json and, when anything changed, $RUNNER_TEMP/NCVEC_CHANGES.md and
  changed=true to $GITHUB_OUTPUT.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, unquote

BASE = "https://ncvec.org/"
UA = {"User-Agent": "ham-radio-flashcards pool watcher (+https://github.com)"}
POOL_RE = re.compile(r"(\d{4})\s*-\s*(\d{4})[\s-]+(technician|general|extra)", re.I)
QID_RE = re.compile(r"\b[TGE][0-9][A-Z][0-9]{2}\b")
REMOVE_RE = re.compile(r"withdrawn|deleted|removed from (the )?pool|removed from use", re.I)
BLOCK = {"p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "h5", "td", "table", "ul", "ol"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.parts, self._a = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._a = [dict(attrs).get("href", ""), ""]

    def handle_endtag(self, tag):
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a" and self._a:
            self.links.append(tuple(self._a)); self._a = None

    def handle_data(self, data):
        self.parts.append(data)
        if self._a:
            self._a[1] += data

    def text(self):
        t = "".join(self.parts).replace("\xa0", " ")
        return [re.sub(r"\s+", " ", ln).strip() for ln in t.split("\n") if ln.strip()]


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        p = Page(); p.feed(r.read().decode("utf-8", "replace")); return p


def pool_name(s):
    m = POOL_RE.search(unquote(s))
    return f"{m.group(3).lower()}-{m.group(1)}-{m.group(2)}" if m else None


def withdrawn_ids(lines):
    ids = set()
    for ln in lines:
        for sent in re.split(r"(?<=[.;])\s+", ln):
            if REMOVE_RE.search(sent):
                ids.update(QID_RE.findall(sent))
    return sorted(ids)


def main(state_dir):
    os.makedirs(state_dir, exist_ok=True)
    sp = os.path.join(state_dir, "state.json")
    old = json.load(open(sp)) if os.path.exists(sp) else {}
    try:
        home = fetch(BASE)
    except Exception as e:  # network trouble shouldn't break the build
        print(f"WARNING: could not reach NCVEC: {e}"); return
    pages = {}
    for href, label in home.links:
        url = urljoin(BASE, href)
        name = pool_name(url) or pool_name(label)
        if name and "ncvec.org" in url and not url.lower().endswith((".pdf", ".docx")):
            pages.setdefault(name, url)
    new, withdrawn = {}, {}
    for name, url in sorted(pages.items()):
        try:
            p = fetch(url)
        except Exception as e:
            print(f"WARNING: {url}: {e}")
            if name in old:
                new[name] = old[name]; withdrawn[name] = old[name].get("withdrawn", [])
            continue
        lines = p.text()
        docs = sorted({unquote(urljoin(url, h)).split("/")[-1] for h, _ in p.links
                       if h.lower().endswith((".pdf", ".docx", ".doc"))})
        errata = [ln for ln in lines if QID_RE.search(ln) or re.search(r"errata|withdrawn|deleted", ln, re.I)]
        wd = withdrawn_ids(lines)
        fp = hashlib.sha256(json.dumps([docs, errata]).encode()).hexdigest()
        new[name] = {"url": url, "documents": docs, "withdrawn": wd, "fingerprint": fp}
        withdrawn[name] = wd
    if not new:
        print("WARNING: no pool pages found on NCVEC; keeping previous state"); return

    changes = []
    for name in sorted(set(old) | set(new)):
        o, n = old.get(name), new.get(name)
        if o is None:
            changes.append(f"- **{name}**: new pool page found: {n['url']}")
        elif n is None:
            changes.append(f"- **{name}**: pool page no longer listed on ncvec.org")
        elif o["fingerprint"] != n["fingerprint"]:
            added = sorted(set(n["documents"]) - set(o["documents"]))
            wd = sorted(set(n["withdrawn"]) - set(o["withdrawn"]))
            msg = f"- **{name}**: page changed ({n['url']})"
            if added: msg += f"; new documents: {', '.join(added)}"
            if wd: msg += f"; newly withdrawn: {', '.join(wd)}"
            changes.append(msg)

    json.dump(new, open(sp, "w"), indent=1); open(sp, "a").write("\n")
    wp = os.path.join(state_dir, "withdrawn.json")
    prev = json.load(open(wp)) if os.path.exists(wp) else {}
    for name, ids in prev.items():  # withdrawals are permanent; never drop one
        withdrawn[name] = sorted(set(withdrawn.get(name, [])) | set(ids))
    json.dump(withdrawn, open(wp, "w"), indent=1); open(wp, "a").write("\n")
    for name, ids in withdrawn.items():
        print(f"{name}: {len(ids)} withdrawn per NCVEC: {' '.join(ids)}")
    if changes and old:
        body = "NCVEC question pool pages changed:\n\n" + "\n".join(changes) + "\n"
        out = os.environ.get("RUNNER_TEMP", state_dir)
        open(os.path.join(out, "NCVEC_CHANGES.md"), "w").write(body)
        print(body)
        if os.environ.get("GITHUB_OUTPUT"):
            open(os.environ["GITHUB_OUTPUT"], "a").write("changed=true\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ncvec")
