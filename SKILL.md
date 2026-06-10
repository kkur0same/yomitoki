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

Every visible section should serve that outline. If a section adds facts but does not improve the reader's grasp of the outline, shorten it or move the detail to Q&A/code refs.

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

### 2. Read for the Story

Read enough of the paper to fill the private five-line outline. Then scan:

- Introduction for motivation and failure mode.
- Method for the actual mechanism.
- Experiments for the regime where it wins or fails.
- Figures/tables for the few visuals worth carrying into the note.
- Repository or code link for implementation refs.

Do not start by filling every schema field. Start by deciding what the reader must understand.

### 3. Author `analysis.json`

Start from a correctly-shaped skeleton instead of guessing field names:

```bash
python3 scripts/assemble.py --scaffold --out /tmp/yomitoki/<slug>/
```

This writes a valid `analysis.json` + `coderefs.json` + `sections/` stub. Fill in the TODO fields. Use `references/authoring-guide.md` for the field contract and examples. Method subsections should point to `sections/*.html` via `body_html_file`; keep long HTML out of JSON. `assemble.py` validates the shape (types, required fields, `quiz.model_answer` vs `qa.a`, `coderefs` as `{"refs": [...]}`) and reports all problems at once before rendering.

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

If the answer is no, revise the prose first. The checker cannot judge taste.

## Parallel Authoring with Subagents (large papers)

Default to single-context authoring. For a long or dense paper (rough gate: >20 pages, OR >5 method subsections, OR a systems paper with many subsystems), parallelize the expensive part, deep-reading and writing the method subsections, with subagents. Keep the narrative spine and final assembly in ONE context so the note stays coherent.

### When to fan out

- Fan out: long/dense paper whose method splits into independent subsections.
- Stay inline: one core mechanism, or subsections that heavily cross-reference each other.

### Procedure

1. **Read for the story (orchestrator).** One story-level pass: intro, method headers, results. Write the five-line outline and Paper Overview yourself. Never delegate the spine.
2. **Plan the fan-out (orchestrator).** Build an assignment table before dispatch: one row per method subsection with its title, its job in the outline, the line range to read, the equations it owns, the figures assigned to it (each figure to exactly one subsection), and the numbers it may cite. Add a short shared-style note: canonical term spellings, "no em-dashes", "explain the hard part first", target depth.
3. **Dispatch one subagent per method subsection (in parallel).** Each gets: the path to `extracted.txt` and its line range, the five-line outline, its assignment row, the shared-style note, and the path to `references/authoring-guide.md`. It authors ONLY its `sections/NN-slug.html`, grounds every claim in the paper text, and returns the file path plus the figures/coderefs it used. Subagents do NOT write `analysis.json`.
4. **Source code refs in parallel.** Dispatch one subagent to find the author repo, map claims to exact line ranges, and return `coderefs.json` entries (see `references/code-ref-waterfall.md`). Keep this separate so refs stay consistent.
5. **Reconcile and author the rest (orchestrator).** Collect the subsection files, resolve duplicate figure/coderef claims, then author the voice-sensitive fields in one pass: TL;DR, overview, timeline, experiments, comparison, limitations, Q&A, quiz. Wire in the subsection files and coderefs.
6. **Assemble, check, self-review (orchestrator)** as in steps 6-7. The `--check` and final taste pass run in one context.

### Subagent dispatch contract (paste into each Agent prompt)

> You are authoring ONE method subsection of a paper reading note. Read {extracted.txt} lines {A-B}. Ground every sentence in that text; do not invent results. Follow the method-subsection rules in {authoring-guide.md}. The note's spine: {five-line outline}. Your subsection: {title} — {its job}. Use only these figures: {ids}. Write the HTML body to {sections/NN-slug.html} and return ONLY: the file path, one line on what you covered, and any figure/coderef you referenced. Match this style: {shared-style note}. Do not write analysis.json.

### Caveats

- Subagents share no context, so every dispatch must be fully self-contained.
- Assign each figure and code ref to exactly one subagent; the checker flags visual duplicates.
- Gate on size: fanning out a short paper costs more than it saves.
- A subagent's final message IS its return value; tell it to return the path, not a prose essay.
- On harnesses with a Workflow tool, the same shape maps to a `pipeline()` with one stage per subsection for deterministic fan-out.

## Reference Files

- `references/authoring-guide.md`: schema field contract and concise writing rules.
- `references/code-ref-waterfall.md`: code reference sourcing, line anchors, snippets.
- `references/diagrams.md`: figure curation and Mermaid safety.
- `scripts/extract.py`: paper extraction.
- `scripts/assemble.py`: HTML rendering and validation.
