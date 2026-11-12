#!/usr/bin/env python3
"""Render a question pool as duplex-printable 8.5x11 flash cards.

Front: question ID, question, choices A-D.
Back:  correct answer letter (same size as the front text) and question ID.
Back pages mirror columns so they line up when duplexed with long-edge flip.
"""
import argparse
import json
import os
from xml.sax.saxutils import escape

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph

FONT_DIRS = ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/liberation2"]


def register_fonts():
    for d in FONT_DIRS:
        reg = os.path.join(d, "LiberationSans-Regular.ttf")
        if os.path.exists(reg):
            pdfmetrics.registerFont(TTFont("LS", reg))
            pdfmetrics.registerFont(TTFont("LSB", os.path.join(d, "LiberationSans-Bold.ttf")))
            pdfmetrics.registerFontFamily("LS", normal="LS", bold="LSB", italic="LS", boldItalic="LSB")
            return
    raise SystemExit("Liberation Sans not found (apt install fonts-liberation)")


PW, PH = letter
COLS, ROWS = 2, 4
CW, CH = 4.0 * inch, 2.5 * inch
MX = (PW - COLS * CW) / 2
MY = (PH - ROWS * CH) / 2
PAD = 0.17 * inch
PER = COLS * ROWS
MAX_PT, MIN_PT = 11.0, 5.5


def figname(f):
    return os.path.splitext(f)[0].upper()


def cell_xy(i, back=False):
    r, c = divmod(i, COLS)
    if back:
        c = COLS - 1 - c
    return MX + c * CW, PH - MY - (r + 1) * CH


def guides(cv):
    cv.setStrokeGray(0.6); cv.setLineWidth(0.4); cv.setDash(2, 3)
    for c in range(COLS + 1):
        x = MX + c * CW; cv.line(x, MY, x, PH - MY)
    for r in range(ROWS + 1):
        y = MY + r * CH; cv.line(MX, y, PW - MX, y)
    cv.setDash()
    cv.setStrokeGray(0); cv.setLineWidth(0.5)
    for c in range(COLS + 1):
        x = MX + c * CW
        cv.line(x, PH - MY + 4, x, PH - 6); cv.line(x, MY - 4, x, 6)
    for r in range(ROWS + 1):
        y = MY + r * CH
        cv.line(2, y, MX - 3, y); cv.line(PW - MX + 3, y, PW - 2, y)


def question_flow(q, size):
    lead = size * 1.18
    qs = ParagraphStyle("q", fontName="LSB", fontSize=size, leading=lead, spaceAfter=size * 0.5)
    a_s = ParagraphStyle("a", fontName="LS", fontSize=size, leading=lead, leftIndent=size * 1.4,
                         firstLineIndent=-size * 1.4, spaceAfter=size * 0.25)
    txt = escape(q["question"])
    if q.get("figure"):
        fig = figname(q["figure"])
        if fig.lower() not in txt.lower():
            txt += f" <font name='LS'>(See Figure {fig})</font>"
    flow = [Paragraph(txt, qs)]
    for L, a in zip("ABCD", q["answers"]):
        flow.append(Paragraph(f"{L}.&nbsp;&nbsp;{escape(a)}", a_s))
    return flow


def fits(flow, w, h):
    tot = 0
    for f in flow:
        _, fh = f.wrap(w, h)
        tot += fh + f.getSpaceAfter()
    return tot <= h


def load_figure(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        im = Image.alpha_composite(Image.new("RGBA", im.size, "white"), im)
    im = im.convert("L")
    bb = ImageOps.invert(im).point(lambda v: 255 if v > 40 else 0).getbbox()
    if bb:
        im = im.crop((max(0, bb[0] - 20), max(0, bb[1] - 20),
                      min(im.width, bb[2] + 20), min(im.height, bb[3] + 20)))
    return ImageReader(im)


class Renderer:
    def __init__(self, pool_dir):
        self.pool_dir = pool_dir
        self.sizes = {}

    def front(self, cv, kind, item, x, y):
        if kind == "fig":
            cv.setFont("LSB", 9); cv.drawString(x + PAD, y + CH - PAD - 7, "Figure " + figname(item))
            cv.drawImage(load_figure(os.path.join(self.pool_dir, item)), x + PAD, y + PAD,
                         CW - 2 * PAD, CH - 2 * PAD - 14, preserveAspectRatio=True, anchor="c")
            return
        q = item
        cv.setFont("LSB", 8); cv.setFillGray(0.35)
        cv.drawString(x + PAD, y + CH - PAD - 6, q["id"]); cv.setFillGray(0)
        w, h = CW - 2 * PAD, CH - 2 * PAD - 13
        size = MAX_PT
        while True:
            flow = question_flow(q, size)
            if fits(flow, w, h) or size <= MIN_PT:
                break
            size -= 0.25
        self.sizes[q["id"]] = size
        Frame(x + PAD, y + PAD, w, h, 0, 0, 0, 0).addFromList(flow, cv)
        if flow:
            raise RuntimeError(f"{q['id']} does not fit on a card")

    def back(self, cv, kind, item, x, y):
        cx = x + CW / 2
        if kind == "fig":
            cv.setFont("LSB", MAX_PT)
            cv.drawCentredString(cx, y + CH / 2 - 4, "Figure " + figname(item))
            return
        sz = self.sizes[item["id"]]
        cv.setFont("LSB", sz)
        cv.drawCentredString(cx, y + CH / 2 - sz * 0.35, item["correct_letter"])
        cv.setFont("LS", 9); cv.setFillGray(0.35)
        cv.drawCentredString(cx, y + PAD + 2, item["id"]); cv.setFillGray(0)


def build(pool_dir, out, title, exclude=()):
    register_fonts()
    pool = json.load(open(os.path.join(pool_dir, "pool.json")))
    pool = [q for q in pool if q["id"] not in set(exclude)]
    cards = [("q", q) for q in pool]
    for fig in sorted({q["figure"] for q in pool if q.get("figure")}):
        cards.append(("fig", fig))
    r = Renderer(pool_dir)
    cv = canvas.Canvas(out, pagesize=letter, invariant=1)  # invariant => reproducible bytes
    cv.setTitle(title); cv.setAuthor("ham-radio-flashcards")
    for p in range(0, len(cards), PER):
        batch = cards[p:p + PER]
        guides(cv)
        for i, (k, it) in enumerate(batch):
            r.front(cv, k, it, *cell_xy(i))
        cv.showPage()
        guides(cv)
        for i, (k, it) in enumerate(batch):
            r.back(cv, k, it, *cell_xy(i, back=True))
        cv.showPage()
    cv.save()
    return len(pool), len(cards) - len(pool), -(-len(cards) // PER)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pool_dir"); ap.add_argument("out"); ap.add_argument("title")
    ap.add_argument("--exclude", nargs="*", default=[])
    a = ap.parse_args()
    print(build(a.pool_dir, a.out, a.title, a.exclude))
