#!/usr/bin/env python3
"""Render a deck_plan.json into slides.pptx strictly through template placeholders.

The plan is the single source of truth.  Rendering is deterministic so the same
plan always yields the same deck.

Plan schema (see references/deck-plan.md for the full contract):
{
  "template": "template.pptx" | null,
  "title": "deck title",
  "language": "zh|en",
  "slides": [
    {
      "layout": "Title Slide" | layout_index | layout_name,
      "title": "page claim as a short assertion",
      "bullets": ["short point", "..."],           // optional
      "picture": {"file": "fig1.png", "caption": "Fig.1 ..."}  // optional
      "picture_right": bool,                        // place picture right of bullets
      "table": {"columns": [...], "rows": [[...]]}, // optional
      "notes": "speaker notes (transitions, emphasis, backup evidence)",
      "evidence": [{"kind":"figure","id":"Fig. 3","locator":"p.5","quote":"..."}]
    }
  ]
}

Usage:
  python3 build_deck.py deck_plan.json -o slides.pptx [--evidence-out evidence_map.json]
"""
import argparse
import json
import os
import sys

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
except ImportError:  # pragma: no cover
    print("ERROR: python-pptx is required: pip install python-pptx", file=sys.stderr)
    sys.exit(2)

GRAY = RGBColor(0x59, 0x59, 0x59)

# PP_PLACEHOLDER type tokens (first token of str(placeholder_format.type))
TITLE_TOKENS = {"TITLE", "CENTER_TITLE"}
SUBTITLE_TOKENS = {"SUBTITLE"}
CONTENT_TOKENS = {"BODY", "OBJECT", "PLACEHOLDER_OBJECT", "CONTENT", "TEXT"}
PICTURE_TOKENS = {"PICTURE", "PLACEHOLDER_PICTURE"}


def ph_token(ph):
    """Return the normalized placeholder type token, e.g. 'TITLE', 'OBJECT'."""
    try:
        return str(ph.placeholder_format.type).upper().split()[0].strip("() ")
    except Exception:
        return ""


def pick_layout(prs, spec, report=None):
    """Resolve a layout by index, exact name, or heuristics from the plan slide role."""
    layouts = [l for m in prs.slide_masters for l in m.slide_layouts]
    if isinstance(spec, int):
        if 0 <= spec < len(layouts):
            return layouts[spec]
    if isinstance(spec, str):
        for l in layouts:
            if l.name == spec:
                return l
    # heuristics: first slide -> title layout, else title+content
    def has(l, t):
        return any(
            getattr(ph.placeholder_format, "type", None) is not None and t in str(ph.placeholder_format.type).lower()
            for ph in l.placeholders
        )
    seen_idx = getattr(pick_layout, "_seen", 0)
    pick_layout._seen = seen_idx + 1
    if seen_idx == 0:
        for l in layouts:
            if "title" in l.name.lower():
                return l
    for l in layouts:
        if "title and content" in l.name.lower():
            return l
    for l in layouts:
        if "title" in l.name.lower() and "content" in l.name.lower():
            return l
    return layouts[0] if layouts else prs.slide_layouts[0]


def set_text(tf, lines, font_size=None):
    tf.clear()
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        if font_size:
            for r in p.runs:
                r.font.size = Pt(font_size)


def fit_picture(slide, pic_path, area_l, area_t, area_w, area_h):
    """Insert picture scaled to fit inside the given inch-area, centered."""
    from PIL import Image  # optional, for aspect ratio
    try:
        with Image.open(pic_path) as im:
            iw, ih = im.size
    except Exception:
        iw, ih = 4, 3
    aspect = iw / ih
    w, h = area_w, area_w / aspect
    if h > area_h:
        h, w = area_h, area_h * aspect
    left = area_l + (area_w - w) / 2
    top = area_t + (area_h - h) / 2
    return slide.shapes.add_picture(pic_path, Inches(left), Inches(top), Inches(w), Inches(h))


def build(plan_path, out_path, evidence_out=None):
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)

    template = plan.get("template")
    prs = Presentation(template) if template and os.path.exists(template) else Presentation()

    # reset deterministic per-run layout cursor
    pick_layout._seen = 0

    evidence_map = []
    warnings = []

    for i, spec in enumerate(plan.get("slides", [])):
        layout = pick_layout(prs, spec.get("layout"))
        slide = prs.slides.add_slide(layout)

        # fill placeholders by type; never add stray text boxes when a
        # matching placeholder exists
        title_done = False
        body_done = False
        picture_done = False
        subtitle_done = False
        body_ph = None
        for ph in slide.placeholders:
            token = ph_token(ph)
            if token in TITLE_TOKENS:
                ph.text = spec.get("title", "")
                title_done = True
            elif token in CONTENT_TOKENS:
                body_ph = ph
            elif token in SUBTITLE_TOKENS:
                # subtitle on a title slide carries the byline bullets
                if not subtitle_done and (spec.get("bullets") or spec.get("subtitle")):
                    lines = spec.get("subtitle") or spec.get("bullets") or []
                    set_text(ph.text_frame, lines if isinstance(lines, list) else [str(lines)])
                    subtitle_done = True
            elif token in PICTURE_TOKENS and spec.get("picture"):
                try:
                    ph.insert_picture(spec["picture"]["file"])
                    picture_done = True
                except Exception as e:
                    warnings.append(f"slide {i+1}: picture placeholder failed ({e}); inline fallback used")

        bullets = spec.get("bullets") or []
        if bullets and body_ph is not None:
            # when the picture sits right of text, keep text in the left 55%
            if spec.get("picture_right") and spec.get("picture"):
                body_ph.width = int(body_ph.width * 0.55)
            set_text(body_ph.text_frame, bullets)
            body_done = True
        elif bullets and subtitle_done:
            pass  # byline bullets already placed in the subtitle placeholder

        if not title_done:
            tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(8.8), Inches(0.9))
            set_text(tb.text_frame, [spec.get("title", "")], font_size=28)
            warnings.append(f"slide {i+1}: no title placeholder; free textbox used (template compliance reduced)")

        pic = spec.get("picture")
        if pic and not picture_done:
            if spec.get("picture_right"):
                area = (5.9, 1.6, 3.5, 4.2)
            else:
                area = (1.2, 1.6, 7.2, 4.3)
            try:
                fit_picture(slide, pic["file"], *area)
                cap = slide.shapes.add_textbox(Inches(area[0]), Inches(area[1] + area[3]), Inches(area[2]), Inches(0.4))
                cap.text_frame.text = pic.get("caption", "")
                for p in cap.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(11)
                        r.font.color.rgb = GRAY
                    p.alignment = PP_ALIGN.CENTER
            except FileNotFoundError as e:
                warnings.append(f"slide {i+1}: picture file missing -> {e}")
        elif pic and picture_done and pic.get("caption"):
            note_add = f"[{pic.get('caption','')}]"
            spec["notes"] = (spec.get("notes", "") + "\n" + note_add).strip()

        tbl = spec.get("table")
        if tbl:
            cols, rows = tbl["columns"], tbl.get("rows", [])
            width, height = 8.8, 0.4 + 0.35 * min(len(rows), 10)
            # sit below the body content (or a two-line title) — never overlap
            if body_ph is not None and bullets:
                top_in = (body_ph.top + body_ph.height) / 914400 + 0.15
            else:
                top_in = 2.3
            if top_in + height > 7.3:
                warnings.append(
                    f"slide {i+1}: table + bullets exceed page height; move the table to its own page or cut bullets to ≤2"
                )
            gt = slide.shapes.add_table(
                len(rows) + 1, len(cols), Inches(0.6), Inches(top_in), Inches(width), Inches(height)
            ).table
            for c, name in enumerate(cols):
                gt.cell(0, c).text = str(name)
            for r, row in enumerate(rows, start=1):
                for c, val in enumerate(row):
                    if c < len(cols):
                        gt.cell(r, c).text = str(val)

        if spec.get("notes"):
            slide.notes_slide.notes_text_frame.text = spec["notes"]

        for ev in spec.get("evidence", []) or []:
            evidence_map.append(
                {
                    "slide": i + 1,
                    "claim": spec.get("title", ""),
                    "kind": ev.get("kind"),
                    "id": ev.get("id"),
                    "locator": ev.get("locator"),
                    "quote": (ev.get("quote") or "")[:300],
                }
            )

    prs.save(out_path)

    if evidence_out:
        with open(evidence_out, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "deck_title": plan.get("title"),
                    "language": plan.get("language"),
                    "pages": len(plan.get("slides", [])),
                    "mappings": evidence_map,
                },
                f,
                ensure_ascii=False,
                indent=1,
            )

    print(json.dumps({
        "slides": len(plan.get("slides", [])),
        "evidence_entries": len(evidence_map),
        "warnings": warnings,
        "out": out_path,
    }, ensure_ascii=False, indent=1))
    return 0 if not warnings else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", help="deck_plan.json")
    ap.add_argument("-o", "--out", default="slides.pptx")
    ap.add_argument("--evidence-out", default=None, help="write evidence_map.json")
    args = ap.parse_args()
    sys.exit(build(args.plan, args.out, args.evidence_out))


if __name__ == "__main__":
    main()
