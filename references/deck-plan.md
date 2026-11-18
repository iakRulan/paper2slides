# deck_plan.json — full schema

`deck_plan.json` is the single source of truth for the deck. `build_deck.py`
renders it deterministically; `check_deck.py` validates it against the paper.

## Top level

| Field | Type | Required | Meaning |
|---|---|---|---|
| `template` | string | no | Path to a .pptx template. Omit or null → builtin 16:9. |
| `title` | string | yes | Deck title (also used on the title slide). |
| `language` | string | no | `"zh"` or `"en"`; keeps bullets/notes consistent. |
| `slides` | array | yes | Ordered page specs. |

## Slide spec

| Field | Type | Required | Meaning |
|---|---|---|---|
| `layout` | string or int | no | Layout name exactly as in `template_report.json`, or a layout index. Default: heuristics (first slide → title layout, else title+content). |
| `title` | string | yes | The page claim, one assertive sentence, ≤ 18 words. |
| `bullets` | string[] | no | ≤ 7 items, ≤ 220 chars each. Speakable phrases, not paragraphs. |
| `picture` | object | no | `{file, caption}`. `file` must exist at build time; `caption` keeps the paper's original label/units. |
| `picture_right` | bool | no | Place the picture right of the bullets (text left ~55%). |
| `table` | object | no | `{columns: string[], rows: string[][]}`. Keep ≤ 8 rows; move big tables to backup. |
| `notes` | string | yes* | Speaker notes: transition, emphasis, backup evidence. Must not duplicate bullets. *Required on content pages by check_deck. |
| `evidence` | array | yes* | ≥ 1 entry per content page. *Title/takeaway pages may carry a section-level entry only. |

## Evidence entry

| Field | Type | Meaning |
|---|---|---|
| `kind` | string | `figure` \| `table` \| `section` \| `equation` |
| `id` | string | Exactly the paper's label, e.g. `Fig. 3`, `Table 2`, `§4.2`. `Fig./Table` ids are validated against `paper_structure.json`. |
| `locator` | string | Where in the paper: `p.5`, `p.5 / §3.1`. |
| `quote` | string | Verbatim sentence (≤ 300 chars) that supports the claim. Copy, never paraphrase numbers. |

## Worked example (excerpt)

```json
{
  "template": "template.pptx",
  "title": "Sparse attention cuts long-context inference cost 3.2x",
  "language": "en",
  "slides": [
    {
      "layout": "Title Slide",
      "title": "Sparse attention cuts long-context inference cost 3.2x",
      "bullets": ["LongLlama-70B · context 128k", "Chen et al., 2026"],
      "notes": "Open with the latency pain the audience knows; this work trades 0.4% accuracy for a 3.2x speedup.",
      "evidence": [{"kind": "section", "id": "Abstract", "locator": "p.1", "quote": "we reduce inference latency by 3.2x at comparable accuracy"}]
    },
    {
      "layout": "Title and Content",
      "title": "Accuracy holds within 0.4% across four benchmarks",
      "bullets": ["Four long-context benchmarks", "Largest drop: 0.4% (QMSUM)"],
      "picture": {"file": "work/fig_p6_0.png", "caption": "Fig. 4 (p.6): accuracy vs. density, units as published"},
      "picture_right": true,
      "notes": "If asked about QMSUM: the drop concentrates on very long summaries; cite §5.2 ablation as backup.",
      "evidence": [{"kind": "figure", "id": "Fig. 4", "locator": "p.6 / §5.1", "quote": "accuracy remains within 0.4% of the dense baseline across all four benchmarks"}]
    }
  ]
}
```
