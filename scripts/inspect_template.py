#!/usr/bin/env python3
"""Inspect a PPTX template: slide sizes, layouts, placeholders.

Produces template_report.json consumed by the deck planning step so every
slide is filled through real placeholders instead of free-floating text boxes.

Usage:
  python3 inspect_template.py template.pptx -o template_report.json
  python3 inspect_template.py --builtin -o template_report.json   # blank 16:9
"""
import argparse
import json
import sys

try:
    from pptx import Presentation
    from pptx.util import Emu
except ImportError:  # pragma: no cover
    print("ERROR: python-pptx is required: pip install python-pptx", file=sys.stderr)
    sys.exit(2)

# PP_PLACEHOLDER enum values (stable numeric ids in OOXML)
PH_TYPES = {
    0: "title", 1: "body", 2: "center_title", 3: "subtitle", 4: "date",
    5: "slide_number", 6: "footer", 7: "chart", 8: "table", 9: "picture",
    10: "media", 11: "org_chart", 12: "object",
}


def emu_in(v):
    return round(Emu(v).inches, 2) if v is not None else None


def describe_placeholder(ph):
    try:
        ph_type = ph.placeholder_format.type
    except Exception:
        ph_type = None
    type_name = PH_TYPES.get(int(ph_type) if ph_type is not None else -1, str(ph_type))
    return {
        "idx": ph.placeholder_format.idx,
        "type": type_name,
        "name": ph.name,
        "pos_in": {
            "left": emu_in(ph.left),
            "top": emu_in(ph.top),
            "width": emu_in(ph.width),
            "height": emu_in(ph.height),
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", nargs="?", help="template .pptx path")
    ap.add_argument("--builtin", action="store_true", help="no template file; use blank 16:9")
    ap.add_argument("-o", "--out", default="template_report.json")
    args = ap.parse_args()

    if args.builtin or not args.template:
        prs = Presentation()
        source = "builtin-default-16x9"
    else:
        prs = Presentation(args.template)
        source = args.template

    report = {
        "source": source,
        "slide_width_in": emu_in(prs.slide_width),
        "slide_height_in": emu_in(prs.slide_height),
        "num_masters": len(prs.slide_masters),
        "layouts": [],
        "notes": [],
    }

    for master_i, master in enumerate(prs.slide_masters):
        for layout_i, layout in enumerate(master.slide_layouts):
            phs = [describe_placeholder(ph) for ph in layout.placeholders]
            report["layouts"].append(
                {
                    "master": master_i,
                    "layout_index": layout_i,
                    "layout_name": layout.name,
                    "placeholders": phs,
                    "placeholder_types": sorted({p["type"] for p in phs}),
                }
            )

    # existing slides (a deck passed as template may already carry content slides)
    for i, slide in enumerate(prs.slides):
        phs = [describe_placeholder(ph) for ph in slide.placeholders]
        report["notes"].append(
            {"slide": i + 1, "layout": slide.slide_layout.name, "placeholders": phs}
        )

    # guidance
    has_title = any("title" in l["placeholder_types"] for l in report["layouts"])
    has_body = any("body" in l["placeholder_types"] for l in report["layouts"])
    has_pic = any("picture" in l["placeholder_types"] for l in report["layouts"])
    tips = []
    if not (has_title and has_body):
        tips.append("Template lacks standard title/body layouts; build_deck will fall back to text boxes on a blank layout and flag reduced template compliance.")
    if not has_pic:
        tips.append("No picture placeholder found; paper figures will be placed as inline pictures centered in the content area.")
    if len(report["layouts"]) <= 2:
        tips.append("Very few layouts available; prefer 'Title Slide' for page 1 and 'Title and Content' elsewhere.")
    report["guidance"] = tips

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(json.dumps({
        "layouts": len(report["layouts"]),
        "names": [l["layout_name"] for l in report["layouts"]],
        "guidance": report["guidance"],
        "out": args.out,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
