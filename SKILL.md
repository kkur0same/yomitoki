---
name: yomitoki
description: "Turn a research paper into a faithful, technical, code-augmented HTML reading note."
---

## First-run welcome

When invoked without a paper:

> **I turn dense research papers into clear, technical HTML study notes.**
>
> Send an arXiv link, arXiv ID, PDF path, PDF URL, or paper title.

If given only a title or natural-language description, search arXiv and confirm the match before proceeding.

## Core Goal

Create a self-contained reading note that helps a technical reader answer:

1. **Why did this paper need to exist?**
2. **What exactly is the move the paper makes?**
3. **Why does that move work?**
4. **Where does it win, by how much, and where does it stop winning?**
5. **How would I start implementing or verifying it?**

The output is HTML, but the job is not to fill an HTML template. The job is to make the paper understandable.

## North Star

Before writing JSON, write a five-line private outline:

```text
Problem:
Old way:
Failure mode:
Paper's move:
Payoff / boundary:
```

The outline sets the through-line: emphasis and order. It does NOT decide coverage. Coverage comes from the contribution inventory in step 2. The outline lets you shorten off-through-line material and push detail to Q&A or code refs; it never licenses dropping a contribution the paper actually makes. Trim decoration, not contributions. A real contribution that sits outside the outline's story still gets its own method subsection or results block, just a shorter one.

## Writing Style

Write like a strong technical blog post:

- Lead with contrast: old method vs. new method, bottleneck vs. fix, assumption vs. failure.
- In the overview, answer only three things first: problem, core solution, main contributions.
- `paper_overview.background` is the motivation block: existing methods, their bottleneck or painpoint, and the root cause.
- Use concrete nouns, numbers, and mechanisms.
- Prefer one sharp paragraph over three complete but low-signal paragraphs.
- Explain the hard part before cataloging components.
- Use paper section / figure / table references when they help verification.
- Keep the reader moving: motivation first, detail second, caveats third.

Avoid:

- Abstract praise: "novel", "important", "powerful", "significant" without a measurable reason.
- Template openings: "This paper proposes...", "The key insight is...", "In summary...".
- Overstuffed TL;DRs that name every contribution, dataset, baseline, and repository.
- Decorative sections included only because the schema has a place for them.
- First-person commentary and emoji in body text.
- Em-dashes in authored prose; use commas, colons, or periods.

## Output Shape

The renderer expects `analysis.json`, `coderefs.json`, method section HTML files, curated figures, and assets. Keep that contract, but let the paper decide how much each section needs.

### Required Reader Sections

- Header metadata.
- Prerequisites, 3-6 concrete concepts with links.
- TL;DR, 2-3 sentences.
- Paper Overview: problem, background, solution, contributions.
- Tech Timeline: 4-6 verified lineage nodes with this paper marked `current`.
- Core Method: method subsections, each with formulas/algorithms/code only when the paper warrants them.
- Experiments / Main Results.
- Methods Comparison or Related Work, whichever best explains the contrast.
- Limitations / Use Cases / Open Questions.
- Q&A and short quiz.

### Optional Sections

Use these only when they clarify the story:

- `where_this_matters`: for foundational primitives used in later systems.
- `jargon`: for terms a hover tooltip genuinely helps. Skip generic terms.

## Workflow

### 1. Extract

```bash
python3 scripts/extract.py <input> --out /tmp/yomitoki/<paper-slug>/
```

Inputs: arXiv URL/ID, local PDF, PDF URL. Outputs include `extracted.txt`, `figures/`, `figures.json`, and a skeleton `analysis.json`.

Do two passes in order: first an inventory (decides coverage), then the spine (decides emphasis). Keeping these separate is what stops the five-line outline from silently dropping a real contribution that does not fit the chosen story.

**Pass A, contribution inventory (coverage).** Before writing the outline, list every contribution-bearing unit the paper has:

1. Copy the paper's own stated contributions verbatim, usually a numbered list at the end of the introduction or in the abstract.
2. Walk the section headings and add any section that introduces its own mechanism, algorithm, training or inference system, or a distinct result, even if it is far from the headline.

For each inventory item, mark **cover deeply / cover briefly / omit** with a one-line reason. Default to covering anything the authors list as a contribution or that has its own method or results. Only omit true boilerplate: related-work surveys you have already folded in, reproducibility appendices, acknowledgments. A multi-part systems or model paper usually has contributions in architecture, training, post-training, infrastructure, AND evaluation; an architecture-heavy read must not swallow the training, post-training, or systems contributions. If the paper's headline is one theme (e.g. efficiency), that theme sets emphasis, not the boundary of what exists.

**Pass B, five-line spine (emphasis).** Now fill the private outline (Problem / Old way / Failure mode / Paper's move / Payoff). The spine orders and weights the inventory; it does not prune it.

Then scan for detail:

- Introduction for motivation and failure mode.
- Method for the actual mechanism.
- Experiments for the regime where it wins or fails, and for comparison against the baselines the paper actually reports (including closed or proprietary systems, not only the authors' own prior models).
- Figures/tables for the few visuals worth carrying into the note.
- Repository or code link for implementation refs.

Do not start by filling every schema field. Start by deciding what the reader must understand, and from the inventory, what the note must cover.

### 3. Author `analysis.json`

Use `references/authoring-guide.md` for the field contract and examples. Method subsections should point to `sections/*.html` via `body_html_file`; keep long HTML out of JSON.

Good method subsections usually follow:

1. What problem this part solves.
2. The mechanism, with the smallest useful formula or diagram.
3. A concrete scale/cost/shape.
4. Pseudocode and runnable code when the paper defines an algorithm.
5. One design-rationale paragraph when the choice is non-obvious.

### 4. Author `coderefs.json`

Use `references/code-ref-waterfall.md`.

Priority:

1. Exact author-repo line ranges for the paper's implementation.
2. High-quality external implementations or tutorials.
3. Synthesized snippets only for baselines, toy demonstrations, or when no real implementation exists.

Real refs should be line-specific and include a short preview. Synthesized snippets must be labeled.

### 5. Curate Figures and Mermaid

Use `references/diagrams.md`.

Pick paper figures that teach the specific paragraph where they appear or carry a result. Do not select a figure because the page "needs an architecture diagram." If the paper has no architecture figure, use a Mermaid schematic only when the architecture or flow is actually in the paper. Place each method figure near the prose it explains with `anchor_phrase`; otherwise leave it out or put it in the correct non-method section.

### 6. Assemble and Check

```bash
python3 scripts/assemble.py \
  --analysis /tmp/yomitoki/<slug>/analysis.json \
  --coderefs /tmp/yomitoki/<slug>/coderefs.json \
  --figures /tmp/yomitoki/<slug>/figures/ \
  --assets assets \
  --out ./yomitoki-out/<slug>/ \
  --check
```

The checker's pass/fail rules are documented in `references/authoring-guide.md`. Do not read `scripts/assemble.py` to learn them; author from the guide and let `--check` report problems.

Fix all hard failures. Warnings are acceptable only when the choice is deliberate and explained in `visual_notes` or by the paper's structure.

### 7. Final Self-Review

Before calling the note done, read the TL;DR, Overview, and first method subsection as a reader. Ask:

- Can the reader explain the problem and the fix in five minutes?
- Does the contrast with prior methods appear before implementation detail?
- Are the strongest numbers tied to the regime where they apply?
- Are code refs real and line-specific when a repo exists?
- Did any section become a checklist rather than an explanation?

Then run a **coverage pass** against the step-2 inventory. For every item marked "cover", confirm it actually appears in the note (a method subsection, a results row or table, or a named paragraph). For every "omit", confirm the reason still holds. An item in the paper's own contribution list that is absent from the note is a bug: add it before shipping. `assemble.py --check` validates structure, not coverage, so this is the only gate that catches a dropped contribution.

If the answer is no, revise the prose first. The checker cannot judge taste.

## Reference Files

- `references/authoring-guide.md`: schema field contract and concise writing rules.
- `references/code-ref-waterfall.md`: code reference sourcing, line anchors, snippets.
- `references/diagrams.md`: figure curation and Mermaid safety.
- `scripts/extract.py`: paper extraction.
- `scripts/assemble.py`: HTML rendering and validation.
