#!/usr/bin/env python3
"""Check a generated deck (slides.pptx + deck_plan.json) before delivery.

Verifies, per slide:
  - non-empty title and title length budget
  - bullets exist and stay inside the information-density budget
  - speaker notes present and NOT a copy of the slide text
  - every evidence entry has kind/id/locator
  - every referenced figure (evidence id like "Fig. 3") exists in the
    paper structure produced by pdf_extract.py (when --paper given)
  - picture files referenced by the plan exist

Usage:
  python3 check_deck.py deck_plan.json slides.pptx --paper paper_structure.json -o check_report.json
"""
import argparse
import json
import os
import re
import sys

try:
    from pptx import Presentation
except ImportError:  # pragma: no cover
    print("ERROR: python-pptx is required: pip install python-pptx", file=sys.stderr)
    sys.exit(2)

MAX_TITLE_WORDS = 18
MAX_BULLET_CHARS = 220
MAX_BULLETS = 7


def slide_text(slide):
    parts = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            parts.append(sh.text_frame.text)
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan")
    ap.add_argument("deck")
    ap.add_argument("--paper", default=None, help="paper_structure.json from pdf_extract.py")
    ap.add_argument("-o", "--out", default="check_report.json")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)

    paper = None
    if args.paper and os.path.exists(args.paper):
        with open(args.paper, encoding="utf-8") as f:
            paper = json.load(f)
    known_figs = {f["label"] for f in (paper or {}).get("figures", [])}
    known_tabs = {t["label"] for t in (paper or {}).get("tables", [])}

    prs = Presentation(args.deck)
    issues = []
    stats = {"slides": len(plan.get("slides", [])), "built": len(prs.slides), "notes": 0, "evidence": 0, "pictures": 0}

    if stats["built"] != stats["slides"]:
        issues.append(f"plan has {stats['slides']} slides but deck built {stats['built']}")

    for i, spec in enumerate(plan.get("slides", [])):
        sid = i + 1
        title = (spec.get("title") or "").strip()
        if not title:
            issues.append(f"slide {sid}: missing title")
        elif len(title.split()) > MAX_TITLE_WORDS:
            issues.append(f"slide {sid}: title too long ({len(title.split())} words > {MAX_TITLE_WORDS})")

        bullets = spec.get("bullets") or []
        if len(bullets) > MAX_BULLETS:
            issues.append(f"slide {sid}: too many bullets ({len(bullets)} > {MAX_BULLETS})")
        for b in bullets:
            if len(b) > MAX_BULLET_CHARS:
                issues.append(f"slide {sid}: bullet over {MAX_BULLET_CHARS} chars (paragraph pasted instead of rewritten?)")
        # rendered-deck consistency: first bullet must actually appear on the slide
        if bullets and i < stats["built"]:
            rendered = slide_text(prs.slides[i])
            first = bullets[0].strip()[:60]
            if first and first not in rendered.replace("\n", " ") and first not in rendered:
                issues.append(f"slide {sid}: bullet text missing from rendered deck (placeholder not filled?)")

        notes = (spec.get("notes") or "").strip()
        if notes:
            stats["notes"] += 1
            slide_words = set(re.findall(r"\w+", slide_text(prs.slides[i]).lower())) if i < stats["built"] else set()
            note_words = set(re.findall(r"\w+", notes.lower()))
            overlap = len(slide_words & note_words) / max(1, len(note_words))
            if overlap > 0.8 and len(note_words) > 6:
                issues.append(f"slide {sid}: notes duplicate the slide text ({overlap:.0%} overlap)")

        if not spec.get("evidence"):
            issues.append(f"slide {sid}: no evidence entry (page must cite its source)")
        else:
            for ev in spec["evidence"]:
                stats["evidence"] += 1
                for field in ("kind", "id", "locator"):
                    if not ev.get(field):
                        issues.append(f"slide {sid}: evidence missing '{field}'")
                eid = (ev.get("id") or "").strip()
                if paper and eid:
                    if re.match(r"(?i)^fig", eid) and known_figs and eid not in known_figs:
                        issues.append(f"slide {sid}: '{eid}' not found in paper figures {sorted(known_figs)}")
                    if re.match(r"(?i)^table", eid) and known_tabs and eid not in known_tabs:
                        issues.append(f"slide {sid}: '{eid}' not found in paper tables {sorted(known_tabs)}")

        if spec.get("table") and len(bullets) > 2:
            issues.append(f"slide {sid}: table page carries {len(bullets)} bullets (>2) — split or trim; density check")

        pic = spec.get("picture")
        if pic:
            if not os.path.exists(pic.get("file", "")):
                issues.append(f"slide {sid}: picture file missing: {pic.get('file')}")
            else:
                stats["pictures"] += 1
            if pic.get("file") and not pic.get("caption"):
                issues.append(f"slide {sid}: picture without caption (keep original numbering/units)")

    # page-count budget: task limits usually cap decks; warn above 20
    if stats["slides"] > 20:
        issues.append(f"deck has {stats['slides']} pages; confirm the task's page limit allows this")

    report = {
        "ok": not issues,
        "stats": stats,
        "issues": issues,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
