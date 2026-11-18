#!/usr/bin/env python3
"""Extract structured text, sections, figures and tables from a paper PDF.

Output: one JSON document with
  - pages: per-page plain text
  - sections: heading candidates with page + y-position
  - figures/tables: caption candidates with page, index and bbox
  - abstract / keywords when detectable

Usage:
  python3 pdf_extract.py input.pdf -o paper_structure.json
"""
import argparse
import json
import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    print("ERROR: PyMuPDF is required: pip install pymupdf", file=sys.stderr)
    sys.exit(2)

HEADING_RE = re.compile(
    r"^(?:(\d+(?:\.\d+)*)\.?\s+)?([A-Z][A-Za-z0-9 ,:\-\(\)/]{3,90})$"
)
CAPTION_FIG_RE = re.compile(r"^\s*(Fig(?:ure)?\.?\s*(\d+)[\.:]?)", re.IGNORECASE)
CAPTION_TAB_RE = re.compile(r"^\s*(Table\s*(\d+)[\.:]?)", re.IGNORECASE)


def heading_level(text: str):
    """Return (level, title) if line looks like a section heading, else None."""
    m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.{3,100})$", text)
    if m:
        depth = m.group(1).count(".") + 1
        title = m.group(2).strip()
        if len(title.split()) <= 18 and not title.endswith((",", ";")):
            return depth, f"{m.group(1)} {title}"
    # unnumbered common headings
    unnumbered = {
        "abstract", "summary", "introduction", "background", "related work",
        "methods", "methodology", "materials and methods", "results",
        "results and discussion", "discussion", "conclusion", "conclusions",
        "conclusion and outlook", "limitations", "acknowledgments",
        "acknowledgements", "references", "appendix", "future work",
        "experimental setup", "experiments", "evaluation", "overview",
        "motivation", "preliminaries", "proposed method", "approach",
    }
    t = text.strip().lower().rstrip(".")
    if t in unnumbered and len(text.strip()) <= 40:
        return 1, text.strip().rstrip(".")
    return None


def extract(pdf_path: str):
    doc = fitz.open(pdf_path)
    out = {
        "source": pdf_path,
        "num_pages": doc.page_count,
        "metadata": {k: v for k, v in (doc.metadata or {}).items() if v},
        "pages": [],
        "sections": [],
        "figures": [],
        "tables": [],
        "abstract_text": None,
    }

    for pno in range(doc.page_count):
        page = doc[pno]
        pw, ph = page.rect.width, page.rect.height
        blocks = page.get_text("dict")["blocks"]
        page_text_parts = []
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                y = line["bbox"][1]
                size = max((s.get("size", 0) for s in spans), default=0)
                font = next((s.get("font", "") for s in spans), "")
                page_text_parts.append(
                    {"text": text, "y": round(y, 1), "size": round(size, 1), "font": font}
                )
        page_text_parts.sort(key=lambda d: d["y"])
        out["pages"].append(
            {
                "page": pno + 1,
                "width": round(pw, 1),
                "height": round(ph, 1),
                "lines": page_text_parts,
            }
        )

    # headings + captions from assembled lines
    for pg in out["pages"]:
        pno = pg["page"]
        body_sizes = sorted(l["size"] for l in pg["lines"])
        median_size = body_sizes[len(body_sizes) // 2] if body_sizes else 10.0
        for line in pg["lines"]:
            text = line["text"]
            # captions
            mf = CAPTION_FIG_RE.match(text)
            if mf:
                out["figures"].append(
                    {
                        "label": f"Fig. {mf.group(2)}",
                        "page": pno,
                        "y": line["y"],
                        "caption_start": text[:220],
                    }
                )
                continue
            mt = CAPTION_TAB_RE.match(text)
            if mt:
                out["tables"].append(
                    {
                        "label": f"Table {mt.group(2)}",
                        "page": pno,
                        "y": line["y"],
                        "caption_start": text[:220],
                    }
                )
                continue
            # headings: numbered, or bold/larger than body
            h = heading_level(text)
            if h:
                depth, title = h
                out["sections"].append(
                    {
                        "level": depth,
                        "title": title,
                        "page": pno,
                        "y": line["y"],
                    }
                )
            elif (
                line["size"] >= median_size + 2.5
                and 3 <= len(text.split()) <= 20
                and not text.endswith((".", ",", ";", ":"))
                and "@" not in text
                and len(out["sections"]) < 200
            ):
                out["sections"].append(
                    {"level": 2, "title": text, "page": pno, "y": line["y"]}
                )

    # abstract: text between "Abstract" heading and next heading
    secs = out["sections"]
    for i, s in enumerate(secs):
        if s["title"].strip().lower() == "abstract":
            start = s
            end = next((x for x in secs[i + 1:] if x["page"] > s["page"] or x["y"] > s["y"]), None)
            collected = []
            for pg in out["pages"]:
                if pg["page"] < s["page"]:
                    continue
                if end and (pg["page"] > end["page"]):
                    break
                for line in pg["lines"]:
                    if pg["page"] == s["page"] and line["y"] <= s["y"]:
                        continue
                    if end and pg["page"] == end["page"] and line["y"] >= end["y"]:
                        continue
                    if line["text"].strip():
                        collected.append(line["text"])
            out["abstract_text"] = " ".join(collected)[:3000]
            break

    # dedupe captions keeping first occurrence per label
    for key in ("figures", "tables"):
        seen = set()
        uniq = []
        for item in out[key]:
            if item["label"] not in seen:
                seen.add(item["label"])
                uniq.append(item)
        out[key] = uniq

    return out


def section_text(structure: dict, title_substring: str, max_chars: int = 4000):
    """Return concatenated body text between the matched heading and the next heading."""
    secs = structure["sections"]
    target = None
    for i, s in enumerate(secs):
        if title_substring.lower() in s["title"].lower():
            target = i
            break
    if target is None:
        return None
    start, end = secs[target], None
    for s in secs[target + 1:]:
        if s["level"] <= start["level"]:
            end = s
            break
    parts = []
    for pg in structure["pages"]:
        if pg["page"] < start["page"]:
            continue
        if end and pg["page"] > end["page"]:
            break
        for line in pg["lines"]:
            if pg["page"] == start["page"] and line["y"] <= start["y"]:
                continue
            if end and pg["page"] == end["page"] and line["y"] >= end["y"]:
                continue
            parts.append(line["text"])
    text = " ".join(parts)
    return text[:max_chars]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", help="input paper PDF")
    ap.add_argument("-o", "--out", default="paper_structure.json")
    args = ap.parse_args()

    structure = extract(args.pdf)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=1)

    # short human summary on stdout
    print(
        json.dumps(
            {
                "pages": structure["num_pages"],
                "sections": len(structure["sections"]),
                "figures": [f["label"] for f in structure["figures"]],
                "tables": [t["label"] for t in structure["tables"]],
                "has_abstract": bool(structure["abstract_text"]),
                "out": args.out,
            },
            ensure_ascii=False,
            indent=1
        )
    )


if __name__ == "__main__":
    main()
