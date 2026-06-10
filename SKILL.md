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

The note must be:

- **Complete**: cover the core technical details and explain the actual contribution. 
- **Accurate**: grounded in the paper, with no unsupported claims.
- **Readable**: calm technical-blog voice, deep but easy to follow.
- **Reflective**: use analysis, Q&A, and quiz to help readers understand design choices, limits, and transfer.


## Writing Style

### Do

1. **Use precise technical language.** Standard terminology from the field. Match formulas and symbols to the paper. Describe technical details without ambiguity.
2. **Make hard ideas understandable.** Give intuition before the formula. Use a concrete example or analogy when it reduces confusion. Explain every formula variable, symbol by symbol.
3. **Organize clearly.** Keep a visible logical hierarchy. Make important points easy to find. Use diagrams, tables, and code only when they reduce explanation cost.
4. **Add real analysis.** Explain why the authors made important design choices. Compare concretely with prior methods. State where the method applies and where it breaks. For non-obvious choices, ask a sharp "Why ...?" question that names the obvious alternative and the tradeoff the choice introduces.

Other style rules:

- Prefer one sharp paragraph over three complete but low-signal paragraphs.
- Use concrete nouns, numbers, and mechanisms.
- Explain the hard part before cataloging components.
- Use paper section / figure / table references when they help verification.
- Keep the reader moving: motivation first, detail second, caveats third.

### Avoid

1. **AI-template phrases.** No "The core contribution is...", "The advantage of this method is...", "In summary...", "It is worth noting...", "This has broad significance...", "This paper proposes...", "The key insight is..." style phrases.
2. **Empty evaluation.** Do not call the work important, novel, powerful, or promising without concrete evidence. No generic "new direction" claims.
3. **Over-decoration.** No emoji in the body. Do not bold every sentence. Avoid deep nested lists unless the paper itself needs them.
4. **Unneeded first person.** Avoid "I think", "my understanding". Keep an objective explanatory voice.
5. **Em-dashes.** Do not use em-dashes in authored prose. Use a period, comma, or parentheses instead.

## Note Structure

The renderer expects `analysis.json`, `coderefs.json`, method section HTML files, curated figures, and assets. Keep that contract, but let the paper decide how much each section needs.

### Token-Efficient Authoring

For long papers, save tokens by changing the working shape, not by weakening the note:

- Persist the coverage plan to `/tmp/yomitoki/<paper-slug>/coverage.md` as the durable source of truth for contribution inventory, section plan, figure candidates, experiment map, and coverage status. (Short papers can keep this plan inline; the file earns its place only when context cannot hold the whole paper.)
- Keep `analysis.json` compact: metadata, short overview fields, lists, tables, refs to `sections/*.html`, and figure/code-ref manifests. Do not put long method prose in JSON.
- Write long explanation in `sections/*.html`, one method or result section at a time. When revising, reopen only `coverage.md`, the relevant paper excerpt, and the target section file.
- Do not keep the whole paper, full note draft, all code refs, and all figures in active context at once. Use the coverage file to remember decisions between passes.
- Never regenerate the whole note to fix one missing section. Patch the specific JSON field, section file, code ref, or figure entry.

### Required Reader Sections

- Header metadata.
- Prerequisites, 3-6 concrete concepts with links.
- TL;DR, 2-3 sentences.
- Paper Overview: problem, background, solution, contributions.
- Tech Timeline: usually 4-6 verified lineage nodes with this paper marked `current`.
- Core Method: method subsections, each with formulas/algorithms/code only when the paper warrants them.
- Experiments / Main Results.
- Methods Comparison or Related Work, whichever best explains the contrast.
- Limitations / Use Cases / Open Questions.
- Q&A and short quiz.

### Optional Sections

Use these only when they clarify the story:

- `where_this_matters`: for foundational primitives used in later systems.
- `jargon`: for terms a hover tooltip genuinely helps. Skip generic terms.

### `analysis.json` Contract

This section defines the `analysis.json` contract and the writing bar. Keep the note narrative-first; the schema supports the story.

**Exact item keys (enforced by `assemble.py --check`).** These are the spots authors most often get wrong; the checker drains all mismatches in one pass and suggests the right key, but get them right up front:

| Field | Container | Each item's keys |
|---|---|---|
| `qa` | list | `{"q", "a", "type"}` (not `question`/`answer`); `type` in: intuition, principle, detail, limit, engineering, extension |
| `quiz` | list | `{"q", "model_answer"}` (not `question`/`answer`/`a`) |
| `limitations` | list | `{"limit"}` objects (not bare strings) |
| `use_cases`, `open_questions` | list | bare strings (not objects) |
| `where_this_matters` | object | `{"items": [{"workload","scale","impact"}, ...]}` (wrap the list in `items`) |
| `related_work.closest_with_delta` | object | `{"title", "key_delta"}` (not `delta`) |
| `prerequisites` | list | `{"term", "brief", ...links}` |
| `tech_timeline` | list | `{"year", "label", "delta", "current"}` |
| `paper_figures` | list | `{"src", "caption", "id", "anchor_section", "anchor_phrase"}` |

Do not invent top-level keys: anything outside the documented set is dropped silently at render (the checker warns, but it still won't appear). For example, a method-section intro belongs in the first `method_subsections[]` entry, not a top-level `method_opening` field. For "missing value" cells in any table, write `n/a`, never an em-dash (authored em-dashes fail `--check`).

#### 0. Header Metadata

Required:

- `title`, `authors`, `venue`, `year`
- `subtitle`: one concrete sentence, not a slogan
- `difficulty`: 1-5
- `difficulty_label`: name what is hard, e.g. `matrix calculus`, not `Advanced`
- `estimated_reading_time`: 12-20 min. Compose it, don't guess: ~3 min for TL;DR + Overview + Timeline, ~2.5 min per method subsection, ~2 min results, ~2 min comparison/related/limits, ~2.5 min Q&A. (5 subsections ≈ 18 min; 3 ≈ 14 min.) Round into the 12-20 range; +1-2 for theory-dense papers.
- `tags`: 3-6 lowercase tags
- preserve `paper_url`, `arxiv_url`, `author_repo` from the skeleton when present

Difficulty:

| Stars | Use when |
|---|---|
| 1 | no specialist background |
| 2 | undergrad ML/CS or one mainstream area |
| 3 | graduate/practitioner depth in one domain |
| 4 | multiple domains or proof-heavy work |
| 5 | narrow expert audience |

#### 1. Prerequisites

3-6 concepts. Each item:

```json
{
  "term": "Backpropagation through computational graphs",
  "brief": "Reverse-mode autodiff: accumulate gradients backward through a recorded graph.",
  "beginner_link": "https://colah.github.io/posts/2015-08-Backprop/",
  "beginner_title": "Calculus on Computational Graphs: Backpropagation (Christopher Olah)",
  "primary_link": "https://www.nature.com/articles/323533a0",
  "primary_title": "Learning representations by back-propagating errors (Rumelhart, Hinton & Williams)"
}
```

Rules:

- Search for a real beginner-friendly resource; do not default to null.
- Use recognizable resource titles plus source/author in parentheses, e.g. `The Illustrated Transformer (Jay Alammar)`.
- Prefer original papers or official docs for primary links. Wikipedia is acceptable for basic concepts.

#### 2. TL;DR

2-3 sentences, about 90 words max. It must contain:

1. The concrete bottleneck or failure mode.
2. The paper's mechanism.
3. The strongest payoff, with the regime where it applies.

Good shape:

```json
"tldr": {
  "summary": "RNN encoder-decoders process tokens sequentially, so long-range dependencies travel through many recurrent steps and training cannot fully parallelize across a sequence. The Transformer removes recurrence and convolution, using scaled dot-product self-attention so each token can directly mix information from every other token in one layer. On WMT 2014 English-to-German, the base model reaches 27.3 BLEU and the big model reaches 28.4 BLEU while training faster than prior architectures."
}
```

Bad shape: a single paragraph that lists every dataset, library, figure, implementation detail, and all speedup numbers.

#### 3. Paper Overview

Renderer schema:

```json
"paper_overview": {
  "problem": "...",
  "background": "...",
  "solution": "...",
  "contributions": ["...", "..."]
}
```

Writing bar:

- `problem`: one paragraph. Name the task and why existing behavior hurts.
- `background`: write it as the painpoint, not a literature survey: what existing methods do, where they break (bottleneck, limit, cost), and the root cause of the problem the paper attacks. Write it as the painpoint that forces the paper to exist, in this order:

1. Existing methods: what do people currently do?
2. Bottleneck / painpoint: what breaks, costs too much, or fails to scale?
3. Root cause: why does that bottleneck exist?
4. Consequence: why does the paper need a different mechanism?

Use a compact taxonomy table when there are several baseline families.
- `solution`: one paragraph naming the actual move.
- `contributions`: 2-5 bolded bullets. Each bullet should be an artifact, mechanism, or result.

Use contrast early. The reader should know what changed before seeing implementation details.

#### 4. Tech Timeline

Usually use 4-6 verified lineage nodes that explain what this paper builds on and, when useful, what it later enables.

```json
"tech_timeline": [
  {"year": 2014, "label": "Seq2Seq", "delta": "Encoder-decoder RNNs make sequence transduction practical."},
  {"year": 2015, "label": "Attention for translation", "delta": "Decoder attends to encoder states instead of using one fixed vector."},
  {"year": 2017, "label": "Transformer", "current": true, "delta": "Replaces recurrence with self-attention and feed-forward blocks."},
  {"year": 2018, "label": "BERT", "delta": "Applies Transformer encoders to bidirectional language pretraining."}
]
```

Rules:

- Mark this paper with `"current": true`.
- Verify each title/year. Drop uncertain nodes.
- Keep each `delta` to one concrete change.
- Do not pad with vague field milestones. If lineage is thin, use fewer nodes, but keep at least one predecessor and this paper.

#### Optional Context Blocks

Use only when helpful:

- `where_this_matters`: foundational primitives or deployment-facing papers. An object `{"items": [ ... ]}` (the list must be wrapped in `items`, with an optional `intro` string) holding 2-4 concrete workloads. Each item is `{"workload": "...", "scale": "...", "impact": "..."}` (e.g. `{"workload": "Diffusion model personalization", "scale": "10-100 images, single consumer GPU", "impact": "Style adapter ships as a 5-50 MB file"}`). Use when the paper introduces a primitive other systems consume (RoPE, LoRA, attention); skip when the paper is the application.

#### 5. Method subsections (the heart of the note)

Complete and deep; cover every major part of the method the paper actually presents, one subsection each. **If the paper presents several algorithms or variants (e.g. plain block → residual block → bottleneck block, or full attention → masked attention → fused-kernel attention), give each its own subsection; don't merge them into one.** Mirror the paper's structure; don't invent sections it lacks. 

**Author each subsection's body in its own `.html` file** and point to it with `body_html_file` (path relative to `analysis.json`); `assemble.py` inlines it. This avoids escaping LaTeX backslashes, quotes, Mermaid arrows, and Python triple-quoted docstrings inside JSON - the biggest authoring time-sink. Use inline `body_html` only for tiny one-paragraph sections.

The canonical shape - `method_subsections` is a thin index, one entry per algorithm/module, each pointing at a file:

```json
"method_subsections": [
  {"title": "Plain block (baseline)",               "body_html_file": "sections/01-plain-block.html"},
  {"title": "Residual block (identity + F(x))",     "body_html_file": "sections/02-residual-block.html"},
  {"title": "Bottleneck block (1×1, 3×3, 1×1)",     "body_html_file": "sections/03-bottleneck-block.html"},
  {"title": "Network architecture (ResNet-50/152)", "body_html_file": "sections/04-architecture.html"}
]
```

The HTML (formulas, pseudocode, runnable Python, Mermaid, Why-question callouts) lives in those `.html` files. `analysis.json` itself stays thin: no long HTML strings.

For each module includes:

- Input and output.
- Core formula or algorithm, with a prose gloss for every symbol.
- Variable-by-variable explanation.
- Pseudocode or code implementation.
- Design-choice analysis: why this choice beats the obvious alternative, and what tradeoff it introduces.

Use "Why..." callouts for non-obvious design choices:

```html
<p><strong>Why keep this state instead of recomputing it?</strong> The state is small enough to stay local, while recomputing would scan the full input again. The tradeoff is extra update arithmetic per element.</p>
```

Good "Why..." questions ask about the actual design choice, compare against the obvious alternative, and mention the tradeoff. Use 1-3 per long method section.

**Pseudocode plus runnable Python.** After any formula or algorithm the paper defines, include both: pseudocode mirroring the paper's listing, then a runnable Python demo verified with an `assert` against a reference or invariant (the assert shows how to test it and proves it was run). This applies to every algorithm the paper presents, baselines included (naive softmax, safe softmax each get their own block, not just the headline contribution). Skip code only for subsections with no formula or algorithm at all (prose discussion, data-sources list). Inline `body_html` carries pseudocode plus the minimal kernel only (roughly <= 20 lines); anything longer (a load/store counter, an assembled layer, a multi-variant benchmark) goes in `coderefs.json` as `source: llm_generated`, anchored from the prose.

##### Key Technical Details

Include when the paper depends on them:

- Training strategy.
- Hyperparameters.
- Implementation tricks.
- Inference tricks.
- Data preprocessing.
- Reproduction risks.

A full worked module deep-dive (Multi-Head Self-Attention: architecture diagram → I/O → named formula blocks → code → design analysis) is in `references/method-example.md`. Read it when authoring the first method section.

#### 6. Experiments and Results

Schema:

```json
"experiments_setup_summary": "...",
"main_results": {
  "headline": "...",
  "table": {"headers": [...], "rows": [...], "highlight_row": 0},
  "ablations": ["..."]
}
```

Writing bar:

- The headline states the result envelope: workload, baseline, metric, and regime.
- Tables should compare regimes, not dump every number.
- Use result figures when the shape of the curve matters.
- Ablations should explain which mechanism earned which gain.
- If the paper's evaluation is narrow, say so.

#### 7. Comparison and Related Work

Use `methods_comparison` when a table helps the reader choose between methods:

```json
"methods_comparison": {
  "headers": ["Method", "Sequential depth", "Long-range path", "This paper's delta"],
  "rows": [["RNN encoder-decoder", "O(n)", "many recurrent steps", "self-attention processes positions in parallel"]],
  "highlight_row": 1,
  "note": "..."
}
```

Use `related_work.closest_with_delta` for the single closest prior: an object `{"title": "...", "key_delta": "..."}` (the field is `key_delta`, not `delta`). The key delta should be precise enough that a reader can explain why this paper was still needed.

#### 8. Limitations, Use Cases, Open Questions

3-5 items each. `limitations` are `{"limit": "..."}` objects; `use_cases` and `open_questions` are bare strings.

- Limitations: assumptions, missing experiments, regimes where the method loses.
- Use cases: concrete places to apply the idea.
- Open questions: what remains unsettled.

Do not duplicate the Q&A. Lists are for scan value; Q&A is for deeper reasoning.

#### 9. Q&A

5-8 questions. Good questions are the points a smart reader might still stumble on after reading the note.

Each item is `{"q": "...", "a": "...", "type": "..."}` (keys `q`/`a`, not `question`/`answer`). Types accepted by renderer:

- `intuition`
- `principle`
- `detail`
- `limit`
- `engineering`
- `extension`

Rules:

- Do not ask "What is the main idea?"
- Use examples, small calculations, or paper numbers.
- If the paper does not settle an answer, say where the evidence stops.
- Use numbered lists when an answer has multiple reasons.

#### 10. Quiz

3-5 self-check items, each `{"q": "...", "model_answer": "..."}` (note `model_answer`, not `a`/`answer`). Ask the reader to derive, compare, or sketch. Multi-line code answers must use markdown fences.

#### Figures

`paper_figures` entries:

```json
{
  "id": "model-architecture",
  "src": "p05_raster_00.png",
  "caption": "Figure 1 - Transformer model architecture. <strong>Shows</strong>: encoder and decoder stacks with multi-head attention, feed-forward layers, residual connections, and normalization. <strong>From paper</strong>: §3.",
  "anchor_section": "method",
  "anchor_phrase": "encoder and decoder stacks"
}
```

Schema rules (`--check` enforces the first two):

- Caption must include `<strong>Shows</strong>` (what the image depicts) and `<strong>From paper</strong>` (the source section/figure).
- `anchor_section` is one of: `header`, `overview`, `motivation`, `method`, `experiments`, `comparison`, `related`, `limits`, `inline`.
- A method figure takes an `anchor_phrase` (verbatim prose from the target section) that positions it before that paragraph; omit it only for a true overview/architecture figure.

Which figures to pick and where to place them: `references/diagrams.md`.

#### Prose Formatting

Allowed inline tags in JSON prose: `<strong>`, `<em>`, `<code>`, `<b>`, `<i>`.

Use emphasis sparingly. Do not bold whole sentences. Avoid em-dashes because `assemble.py --check` treats authored em-dashes as failures.

**Math is KaTeX, never raw text or `<code>`.** Display equations go in `\[ … \]`, inline math in `\( … \)`. Every variable, subscript, superscript, or small expression in prose gets inline KaTeX: write `\(x_i\)`, `\(e^{x_j - m}\)`, `\(\sum_{j=1}^{V} w_j\)`, `\(\max(0,x)\)`, never bare `x_i`, `e^{x_j-m}`, `Σ_j`, or `<code>m_j</code>` (those render as literal carets, underscores, and braces). Use LaTeX commands (`\sum`, `\max`, `\le`, `\cdot`, `\infty`), not Unicode glyphs (`Σ`, `≤`, `·`, `∞`). Reserve `<code>` for identifiers and code, not symbols. The KaTeX auto-renderer ignores `<pre>`/`<code>`, so math inside them stays unrendered. After every display equation, gloss each symbol in prose.

**Long-equation rule.** If a display equation runs past ~10 terms or ~60 KaTeX tokens, split it: factor out the wide part into a second `\[ … \]`, or use `\begin{aligned} … \\ … \end{aligned}`. Two readable lines beat one that scrolls.


## Workflow

### 1. Extract

```bash
python3 scripts/extract.py <input> --out /tmp/yomitoki/<paper-slug>/
```

Inputs: arXiv URL/ID, local PDF, PDF URL. Outputs include `extracted.txt`, `figures/`, `figures.json`, and a skeleton `analysis.json`.

### 2. Plan coverage (inventory + spine)

Build a coverage plan before authoring: the guardrail against dropped sections. For most papers this is inline; for long or multi-pass papers, persist it to `/tmp/yomitoki/<paper-slug>/coverage.md` so decisions survive between passes (short papers do not need the file). Two passes:

**Pass A, inventory (coverage), heading-first.** Enumerate **every section/subsection heading in the paper, in order**, mechanically, one row each (method subsections included). Then copy the paper's stated contributions verbatim and map each onto its heading row(s). A heading that introduces its own formula/algorithm/module/result but maps to no note coverage is a **visible gap**, not a silent omission: this is what catches a deep-dive getting compressed into a "background" paragraph. Mark each row **cover deeply / briefly / omit** with a one-line reason; a heading with its own mechanism defaults to cover-deeply with its own subsection. Omit only true boilerplate (related-work already folded in, reproducibility appendices, acknowledgments). For multi-part systems/model papers, do not let an architecture-heavy read swallow the training, post-training, or systems contributions.

**Pass B, spine (emphasis).** Fill the five-line outline (Problem / Old way / Failure mode / Paper's move / Payoff). The spine orders and weights the inventory; it does not prune it.

The plan (inline, or `coverage.md` for long papers) holds the spine plus these tables:

```text
Spine: Problem / Old way / Failure mode / Paper's move / Payoff

Contribution inventory: | Paper heading (in order) | Stated contribution? | Cover deeply/briefly/omit | Note section | Evidence |
Method section plan:     | Section file | Headings covered | Paper evidence | Code/diagram need |
Experiment map:          | Claim | Metric / dataset / baseline | Paper table/figure | Note placement |
Figure candidates:       | Figure | Keep? | Anchor section | Placement reason |
Coverage checklist:      | Paper heading | Present in note? | Where |
```

### 3. Author Compact `analysis.json`

Use the inline `analysis.json` contract above for the field contract and examples. Method subsections should point to `sections/*.html` via `body_html_file`; keep long HTML out of JSON.

For long papers, treat `analysis.json` as a manifest plus short structured fields:

- Keep TL;DR, overview, timeline, prerequisites, result tables, limitations, Q&A, quiz, `paper_figures`, and method subsection metadata in JSON.
- Put any method or result prose over about 500 characters in `sections/*.html`.
- Prefer several focused `method_subsections` over one large section that tries to carry the whole paper.

### 4. Author Section Files

Write `sections/*.html` one at a time, using the coverage plan to decide scope. Do not load every section draft while authoring the current one.

Each method module must clear the per-module bar in **Method subsections** above (I/O, formula + per-symbol gloss, pseudocode + runnable Python, design-choice callout); that contract is the single source of truth and this step does not restate it. `references/method-example.md` is the full worked example. What is specific to authoring:

- Open the method with an architecture / data-flow map (a paper figure or Mermaid) when the paper has more than one moving part; skip it for a single small mechanism.
- The bar is content, not layout. A single-mechanism paper can deliver it as flowing prose rather than labeled sub-blocks, but it still states input/output and glosses every symbol. Dropping those because the prose "reads fine" without them is how a deep dive quietly degrades into a summary.

After writing each section, mark the heading(s) it covers in the coverage plan (update the `Coverage checklist` in `coverage.md` if you kept the file).

### 5. Author `coderefs.json`

Use `references/code-ref-waterfall.md`.

Priority:

1. Exact author-repo line ranges for the paper's implementation.
2. High-quality external implementations or tutorials.
3. Synthesized snippets only for baselines, toy demonstrations, or when no real implementation exists.

Real refs should be line-specific and include a short preview. Synthesized snippets must be labeled.

### 6. Curate Figures and Mermaid

Use `references/diagrams.md`.

Pick paper figures that teach the specific paragraph where they appear or carry a result. Do not select a figure because the page "needs an architecture diagram." If the paper has no architecture figure, use a Mermaid schematic only when the architecture or flow is actually in the paper. Place each method figure near the prose it explains with `anchor_phrase`; otherwise leave it out or put it in the correct non-method section.

### 7. Assemble and Check

```bash
python3 scripts/assemble.py \
  --analysis /tmp/yomitoki/<slug>/analysis.json \
  --coderefs /tmp/yomitoki/<slug>/coderefs.json \
  --figures /tmp/yomitoki/<slug>/figures/ \
  --assets assets \
  --out ./yomitoki-out/<slug>/ \
  --check
```

Author from this skill's contract and let `--check` report structural problems. Do not read `scripts/assemble.py` to learn the authoring rules.

Fix all hard failures. Warnings are acceptable only when the choice is deliberate and explained in `visual_notes` or by the paper's structure.

### 8. Final Self-Review

Before calling the note done, read the TL;DR, Overview, and first method subsection as a reader. Ask:

- Can the reader explain the problem and the fix in five minutes?
- Does the contrast with prior methods appear before implementation detail?
- Are the strongest numbers tied to the regime where they apply?
- Are code refs real and line-specific when a repo exists?
- Did any section become a checklist rather than an explanation?

Then run a **coverage pass**, walking the paper's section headings **heading by heading** (re-derived straight from the paper, not just the rows you remembered to plan; if you kept `coverage.md`, reconcile it against the paper rather than trusting it). For every heading you chose to cover, confirm it actually appears in the note (a method subsection, a results row or table, or a named paragraph). A heading that introduces its own formula, algorithm, or module must map to its own method subsection, not a sentence inside another section's background. For every heading you chose to omit, confirm the reason still holds. A heading with its own mechanism, or an item in the paper's own contribution list, that is absent from the note is a bug: add it before shipping. `assemble.py --check` validates structure, not coverage, so this heading walk is the only gate that catches a dropped contribution.

If the answer is no, revise the prose first. The checker cannot judge taste.

## Reference Files

- `references/code-ref-waterfall.md`: code reference sourcing, line anchors, snippets.
- `references/diagrams.md`: figure curation and Mermaid safety.
- `references/method-example.md`: full worked module deep-dive (read when authoring the first method section).
- `scripts/extract.py`: paper extraction.
- `scripts/assemble.py`: HTML rendering and validation.
