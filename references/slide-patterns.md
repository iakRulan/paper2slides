# Slide patterns for academic talks

Pick a pattern per page while writing `deck_plan.json`. Each pattern states
its claim shape, typical layout, and what the evidence entry should cite.
A 12-page, 15-minute deck uses roughly: 1×P1, 1×P2, 1×P3, 2×P4, 3×P5, 2×P6,
1×P7, 1×P8, 1×P9 (+2 backup).

| # | Pattern | Claim shape | Typical content | Evidence cites |
|---|---|---|---|---|
| P1 | Title | Who/what/result-in-one-line | Title, authors, venue, one-line takeaway | section: Abstract |
| P2 | Problem | "X costs/fails because Y" | Pain quantified; who suffers; scale | section: Intro numbers |
| P3 | Gap | "Prior work handles A, not B" | 2–3 prior lines, each with its limit | section(s); optional Table |
| P4 | Idea | "Key insight: …" | The one mechanism, one diagram | figure: overview schematic |
| P5 | Method step | "Stage k does Z under C" | Mechanism detail + formula/figure | figure/equation + section |
| P6 | Result-strongest | "Metric improves by N" | Main figure/table, units kept | figure/table: main result |
| P7 | Result-secondary | "Holds across M settings" | Secondary evidence, ablation | figure/table: ablation |
| P8 | Limitation | "Fails when C; cost is R" | Honest scope; what breaks | section: Limitations/Discussion |
| P9 | Takeaway | "Remember these 2 things" | 2–3 bullets, no new claims | section-level |
| B1 | Backup | FAQ answers | Full table, extra plots | figure/table cited by main page |

## Density rules baked into check_deck.py

- Title: one assertive sentence, ≤ 18 words, no bare topic labels.
- Bullets: ≤ 7 per page, ≤ 220 chars — longer means a paragraph was pasted.
- Notes: required on content pages; must not be a copy of the slide text
  (> 80% word overlap is flagged).

## Common failure → pattern fix

| Failure | Fix |
|---|---|
| Paper order mirrored section-by-section | Re-plan with storyline order P1→P9 |
| "Results" page with 12 text bullets | Replace with P6: main figure + 3 bullets |
| Figure on a page it doesn't support | Move figure to a page whose claim it backs, or re-aim the claim |
| Schematic shown as if experimental data | Mark in caption "overview schematic (Fig. 1)" and use P4 |
| Numbers rephrased from memory | Copy the sentence into `evidence.quote`; numbers only from quotes |
