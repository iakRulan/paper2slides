---
name: paper2slides
description: "Turn a research paper (PDF) into a presentable, editable academic slide deck (PPTX + PDF + PNG previews) with per-slide evidence mapping back to the paper. Enforces a five-phase pipeline: structure extraction → storyline planning → template-constrained rendering → automated checks → evidence map. Trigger on: '论文转PPT', '论文转学术PPT', 'paper to slides', 'academic presentation', '把论文做成汇报', '学术汇报PPT', 'turn this paper into a presentation', or any task that requires converting a paper PDF into slides while keeping every page traceable to its source. Not for literature review writing, figure beautification, or paper polishing."
---

# paper2slides — Paper → Academic Slide Deck with Evidence Mapping

Convert a paper PDF into a defensible academic deck. The failure mode this skill exists to prevent: a deck that looks like slides but is really the paper chopped into paragraphs — storyline lost, figure numbers mismatched, numbers silently rewritten, template overridden, notes missing, export broken.

**Method in one line:** extract the paper's structure with a script, plan the deck as a JSON page plan (one claim per page, each claim tied to evidence), then render deterministically through template placeholders and machine-check the result. Quality lives in the plan; layout stability lives in the script.

## When to use

- Input: one or more paper PDFs (or text material), plus an optional .pptx template and constraints (audience, time, page limit).
- Output: `slides.pptx` (editable), `slides.pdf` + PNG previews (rendered proof), `evidence_map.json` (page → source traceability), `deck_plan.json` (the auditable plan), `result.json` (run summary).

## Pipeline (run in order; do not skip phase 2 or 4)

### Phase 1 — Extract the paper's structure (script, not eyeballing)

```bash
python3 scripts/pdf_extract.py paper.pdf -o work/paper_structure.json
```

This yields pages, section headings (numbered + bold), figure/table caption inventory (label, page, first 220 chars), and abstract. Read `paper_structure.json` — do not re-read the raw PDF page by page. If PyMuPDF is missing: `pip install pymupdf`. If the PDF is scanned (few text lines per page), run an OCR pass and say so in `result.json.uncertainty`.

### Phase 2 — Plan the storyline as `deck_plan.json` (the quality bar lives here)

Write `work/deck_plan.json` (schema below). Rules, in priority order:

1. **Storyline, not paper order.** The deck walks: *problem → why prior work falls short → core idea → method → key results (strongest first) → limitations → takeaway*. Reorder freely; never mirror section order 1:1.
2. **One claim per page.** The `title` field is the claim, phrased as a complete assertion ("GNN depth saturates beyond 4 layers"), not a topic label ("Results").
3. **Every content page carries evidence.** `evidence[]` requires `kind` (figure|table|section|equation), `id` (exactly as the paper labels it, e.g. "Fig. 3", "Table 2"), `locator` (page/section), and a short `quote` copied verbatim (≤ 300 chars) backing the claim. Never restate numbers from memory — copy from the extracted text and keep units.
4. **Density budget.** ≤ 7 bullets/page, ≤ 220 chars/bullet. A table page carries ≤ 2 bullets (or move the table to its own page). Long sentences are a smell: rewrite as speakable phrases, keep the full sentence for the notes.
5. **Figures tell the results.** For each results page prefer the paper's own figure/table (`picture.file` = extracted image, `caption` = original label + units). A schematic from the paper is *not* an experimental result — mark it in the caption if used as background.
6. **Notes ≠ slide text.** `notes` carries what the speaker says: transition from the previous page, what to emphasize, backup evidence when questioned. It must not repeat the bullets.
7. **Respect constraints.** Page limit and audience from the task override these defaults. Include the required scaffolding pages (title, outline if > 8 pages, takeaway) within the limit.

```json
{
  "template": "template.pptx",
  "title": "Deck title",
  "language": "zh",
  "slides": [
    {
      "layout": "Title and Content",
      "title": "page claim as an assertion",
      "bullets": ["speakable phrase", "..."],
      "picture": {"file": "work/fig1.png", "caption": "Fig. 1 (p.3): original caption, units kept"},
      "picture_right": true,
      "table": {"columns": ["", "ours", "baseline"], "rows": [["acc", "91.2", "88.4"]]},
      "notes": "transition + emphasis + backup evidence",
      "evidence": [{"kind": "figure", "id": "Fig. 1", "locator": "p.3 / §3.1", "quote": "verbatim sentence ≤300 chars"}]
    }
  ]
}
```

Extract result figures from the PDF as PNGs (flat text is not enough for a deck):

```python
# work/extract_figs.py — prefer native embedded images, else render the page region
import fitz
doc = fitz.open("paper.pdf")
for pno in range(doc.page_count):
    for i, img in enumerate(doc[pno].get_images(full=True)):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        if pix.width < 200 or pix.height < 150:  # skip icons/logos
            continue
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(f"work/fig_p{pno+1}_{i}.png")
```

Cross-check each saved image against `paper_structure.json` captions (same page, position near caption y) before referencing it as "Fig. N". If a caption claims a figure you cannot extract (vector figure, nested subfigures), render the page region above the caption as the image instead, and note it in `result.json.uncertainty`.

### Phase 3 — Inspect the template, then render (script, deterministic)

```bash
python3 scripts/inspect_template.py template.pptx -o work/template_report.json
python3 scripts/build_deck.py work/deck_plan.json -o output/slides.pptx --evidence-out output/evidence_map.json
```

- `inspect_template` lists layouts and placeholders. Set each slide's `layout` from this report — match content to real placeholders (title / body / picture). If no template is given, the builtin 16:9 default is used and `template_compliance` goes into `result.json`.
- `build_deck` fills placeholders only. It never edits master colors or footers. Every plan slide must carry `evidence[]` or the build exits non-zero (warnings listed; fix the plan, not the script).

### Phase 4 — Machine-check, then render previews

```bash
python3 scripts/check_deck.py work/deck_plan.json output/slides.pptx --paper work/paper_structure.json -o work/check_report.json
python3 scripts/render_preview.py output/slides.pptx --outdir output/previews
```

`check_deck` verifies: titles are claims within budget, bullet density, notes are not copies, evidence completeness, figure/table ids exist in the paper, picture files exist, page count. Fix every `issues[]` entry in the **plan** and rebuild — do not hand-edit the .pptx (the plan is the reproducible source).

Open 2–3 PNG previews and look: text cut off? caption under the wrong figure? title overlapping the body? If yes, fix the plan (shorter bullets, `picture_right: true`, smaller table) and rerun phases 3–4.

### Phase 5 — Write the run summary `result.json`

```json
{
  "case_id": "<from /input/case.json when present>",
  "task": "paper-to-slides",
  "status": "complete | partial | failed",
  "deliverables": {
    "deck": "output/slides.pptx",
    "pdf": "output/previews/slides.pdf",
    "previews": "output/previews/pages/",
    "evidence_map": "output/evidence_map.json",
    "plan": "work/deck_plan.json"
  },
  "storyline": ["problem", "gap", "idea", "method", "result 1", "..."],
  "pages": 12,
  "template_compliance": "placeholders-full | placeholders-partial | builtin-default",
  "render": {"pdf_pages": 12, "engine": "libreoffice|pymupdf-only"},
  "checks": {"all_passed": true, "remaining_issues": []},
  "sources": [{"slide": 3, "id": "Fig. 3", "locator": "p.5"}],
  "uncertainty": ["Fig. 4 rendered from page region (vector, not embedded)", "..."],
  "changes": [{"step": "phase4", "fix": "shortened slide 7 bullets to 5"}]
}
```

`status: "partial"` is acceptable and better than a silent gap: list exactly which pages are incomplete and why. Never fabricate figures, numbers, or a rendering state that did not run.

## Failure playbook

| Situation | Action |
|---|---|
| PDF is scanned / text extraction yields < 200 lines total | OCR pass; record it in `uncertainty`; caption ids may be unreliable → verify manually |
| Figure referenced in text not found in captions | Search caption variants ("Figure 4", "Fig. 4.", "Supplementary Fig. S3"); still missing → cite the section instead and note it |
| Formula needed on a slide | Do not retype from the PDF (symbol corruption). Crop the formula region as an image, or use the platform latex-compiler |
| Template lacks picture/body placeholders | `build_deck` falls back to inline placement and downgrades `template_compliance`; keep the fallback, explain in result.json |
| LibreOffice unavailable | Render PDF via soffice is required for previews; if truly unavailable, deliver plan + pptx, set `render.engine = "none"`, state honestly |
| Page limit exceeded | Cut evidence-weak pages first, merge background pages; never shrink below storyline essentials (problem/idea/result/limit/takeaway) |
| Deck > 24 pages for a talk | Ask: audience minutes / 2 = page budget. Long ≠ good; density checks will flag |

## Output contract (files under /app/output when run on the platform)

- `slides.pptx` — editable deck, template placeholders intact
- `previews/slides.pdf`, `previews/pages/*.png` — real rendered proof
- `evidence_map.json` — per-page source mapping (also embedded in speaker-note metadata)
- `result.json` — run summary per the schema above

## Self-check before declaring done

1. `check_report.json` has zero issues.
2. Previews open; spot-check 3 pages visually.
3. Every page's claim is supported by its evidence quote — read quote vs claim once.
4. Notes exist on every content page and are not bullet copies.
5. `result.json` status/uncertainty are honest.
