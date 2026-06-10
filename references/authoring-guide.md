# Authoring Guide

This guide defines the `analysis.json` contract and the writing bar. Keep the note narrative-first; the schema supports the story.

## Narrative Pass First

Before filling fields, write this private outline:

```text
Problem:
Old way:
Failure mode:
Paper's move:
Payoff / boundary:
```


## Header Metadata

Required:

- `title`, `authors`, `venue`, `year`
- `subtitle`: one concrete sentence, not a slogan
- `difficulty`: 1-5
- `difficulty_label`: name what is hard, e.g. `matrix calculus`, not `Advanced`
- `estimated_reading_time`: 12-20 min
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

## Prerequisites

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

## TL;DR

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

## Paper Overview

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
- `background`: this is the motivation. The visible label reads "Background", but write it as the painpoint, not a literature survey: what existing methods do, where they break (bottleneck, limit, cost), and the root cause of the problem the paper attacks.
- `solution`: one paragraph naming the actual move.
- `contributions`: 2-5 bullets. Each bullet should be an artifact, mechanism, or result.

Use contrast early. The reader should know what changed before seeing implementation details.

### Background Field Pattern

`background` is the motivation block (the renderer just labels it "Background"). Write it as the painpoint that forces the paper to exist, in this order:

1. Existing methods: what do people currently do?
2. Bottleneck / painpoint: what breaks, costs too much, or fails to scale?
3. Root cause: why does that bottleneck exist?
4. Consequence: why does the paper need a different mechanism?

Use a compact taxonomy table when there are several baseline families. Adapt the columns to the paper:

| Family | Representatives | Idea | Bottleneck |
|---|---|---|---|
| Full optimization | exact solver, exhaustive search | solve the complete objective | wastes work when only a small answer is needed |
| Streaming / greedy | online heuristic | update a small state per item | can fail under skewed inputs |
| Partition / prune | bucket, sample, threshold | discard irrelevant regions | control logic or bad choices can dominate |

If it's algorithm related, can list the time/space complexity if known (must ground in paper).

## Tech Timeline

Required. Use 4-6 verified lineage nodes that explain what this paper builds on and, when useful, what it later enables.

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

## Optional Context Blocks

Use only when helpful:

- `where_this_matters`: foundational primitives or deployment-facing papers. 2-4 concrete workloads.
- `jargon`: 6-15 useful terms. Skip terms obvious to the target reader. Tooltips should clarify, not decorate.

## Method Subsections

Schema:

```json
"method_subsections": [
  {"title": "Scaled dot-product attention", "body_html_file": "sections/01-scaled-attention.html"},
  {"title": "Multi-head attention", "body_html_file": "sections/02-multi-head.html"}
]
```

The method section should make the paper reconstructable. Use the paper's own structure when it is clear, but make sure the reader can trace:

```text
problem pressure -> mechanism -> state/data flow -> exact operation -> implementation check
```

### Method Opening

Start the method with a compact map when the paper has more than one moving part:

- A paper figure or faithful Mermaid diagram when it reduces working memory.
- A data-flow paragraph: input -> intermediate state -> output.
- A module list: what each part owns.
- The main contrast with the old method.

Skip a generic overview if the paper has one small mechanism. Go straight to the mechanism.

### Core Module Deep Dives

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

If the paper defines an algorithm, include pseudocode. If a small executable version helps verify the idea, include a runnable check with an `assert` against a reference or invariant. Keep inline code short; put longer demos and benchmark harnesses in `coderefs.json`.

### Key Technical Details

Include when the paper depends on them:

- Training strategy.
- Hyperparameters.
- Implementation tricks.
- Inference tricks.
- Data preprocessing.
- Reproduction risks.

## Experiments and Results

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

## Comparison and Related Work

Use `methods_comparison` when a table helps the reader choose between methods:

```json
"methods_comparison": {
  "headers": ["Method", "Sequential depth", "Long-range path", "This paper's delta"],
  "rows": [["RNN encoder-decoder", "O(n)", "many recurrent steps", "self-attention processes positions in parallel"]],
  "highlight_row": 1,
  "note": "..."
}
```

Use `related_work.closest_with_delta` for the single closest prior. The key delta should be precise enough that a reader can explain why this paper was still needed.

## Limitations, Use Cases, Open Questions

3-5 items each.

- Limitations: assumptions, missing experiments, regimes where the method loses.
- Use cases: concrete places to apply the idea.
- Open questions: what remains unsettled.

Do not duplicate the Q&A. Lists are for scan value; Q&A is for deeper reasoning.

## Q&A

5-8 questions. Good questions are the points a smart reader might still stumble on after reading the note.

Types accepted by renderer:

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

## Quiz

3-5 self-check items. Each item is an object with exactly these fields:

```json
{"q": "Derive ... / Compare ... / Sketch ...", "model_answer": "..."}
```

The answer field is `model_answer`, NOT `a` (that is the Q&A field). Using `a`
renders a blank "Model answer." in the page; `assemble.py` now flags this as a
schema error. Ask the reader to derive, compare, or sketch. Multi-line code
answers must use markdown fences.

## Figures

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

Rules:

- Pick figures by meaning, not by quota. A figure belongs only if you can say "this image explains the next paragraph" or "this image carries the result better than a table."
- Do not relabel a non-architecture plot as an architecture diagram just because the method section lacks a visual. If the paper has no architecture figure, either add a faithful Mermaid schematic from the paper text or skip the architecture visual.
- Do not include visually duplicate paper figures unless each adds a condition, metric, or viewpoint.
- Captions must include `Shows` and `From paper`.
- `anchor_section`: `header`, `overview`, `motivation`, `method`, `experiments`, `comparison`, `related`, `limits`, or `inline`.
- For method figures, `anchor_phrase` positions the figure before the matching paragraph. Treat a missing method `anchor_phrase` as a deliberate exception for a true overview/architecture figure only. Most method figures should be anchored to the paragraph they explain.
- Before selecting a figure, inspect it and write a one-line placement reason in your notes: `Figure X -> method/attention because it shows the tensor flow through the module`. If no such reason exists, skip it.

## Prose Formatting

Allowed inline tags in JSON prose: `<strong>`, `<em>`, `<code>`, `<b>`, `<i>`.

Use emphasis sparingly. Do not bold whole sentences. Avoid em-dashes because `assemble.py --check` treats authored em-dashes as failures.

## Final Taste Check

Before assembly, read the TL;DR and Overview alone. They should answer:

- What was broken?
- What changed?
- Why does the change work?
- What is the strongest measured payoff?
- Where is the boundary?

If not, fix those sections before adding more detail.
