# Self-test record (example output — NOT a formal platform case result)

To validate the skill end-to-end before submission, the full pipeline was run
locally on **arXiv:1706.03762** (*Attention Is All You Need*, 15 pages, two-column).

## Input → commands

```bash
curl -sL https://arxiv.org/pdf/1706.03762 -o work/paper.pdf
python3 scripts/pdf_extract.py work/paper.pdf -o work/paper_structure.json
# ... wrote work/deck_plan.json following SKILL.md phase 2 (6 pages, 8 evidence entries)
python3 scripts/build_deck.py work/deck_plan.json -o output/slides.pptx --evidence-out output/evidence_map.json
python3 scripts/check_deck.py work/deck_plan.json output/slides.pptx --paper work/paper_structure.json -o work/check_report.json
python3 scripts/render_preview.py output/slides.pptx --outdir output/previews
```

## What pdf_extract found

- 24 section headings, abstract captured
- Figure inventory: `Fig. 1` (p.3 architecture), `Fig. 2` (p.4 attention), `Fig. 3–5` (appendix, vector)
- Table inventory: `Table 1–4`, all with page numbers and caption prefixes

## Iteration the guards caught (evidence the method self-corrects)

1. First build: the title-slide **subtitle placeholder was misclassified as a title**
   (`"title" in "subtitle"` substring bug) → title duplicated, byline bullets lost.
   Fixed with exact placeholder-token matching; new `check_deck` rule now verifies
   the first bullet actually appears in the rendered deck.
2. Second build: **body placeholder type `OBJECT` was missed** → bullets silently
   dropped, picture rendered full-width. Fixed by matching `OBJECT` as a content token.
3. Third build: **table overlapped a two-line title**, then a table+bullets page
   exceeded page height — the build-time guard fired and refused, per the SKILL.md
   density rule ("a table page carries ≤ 2 bullets"); the plan was fixed by moving
   interpretation lines into speaker notes.

## Final verified output

- `slides.pptx`: 6 slides, 2 embedded paper figures with original-caption labels, 6 speaker notes, 8 evidence entries
- `check_report.json`: `ok: true`, zero issues
- `previews/slides.pdf` + 6 PNG pages: visually spot-checked (title/byline split, text-left/figure-right, table page clean)
- `result.json`: `status: complete`, engine `libreoffice + pymupdf`

This run is included as the worked example of the interface. Platform case runs
follow the same commands with `/input/case.json` inputs and write `/app/output`.
