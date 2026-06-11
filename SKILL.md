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

- For long or multi-pass papers, save the coverage plan to `/tmp/yomitoki/<paper-slug>/coverage.md`. 
- Keep `analysis.json` compact: metadata, short overview fields, lists, tables, refs to `sections/*.html`, and figure/code-ref manifests. Do not put long method prose in JSON.
- Write long explanation in `sections/*.html`, one method or result section at a time. When revising, reopen only `coverage.md`, the relevant paper excerpt, and the target section file.
- Use the coverage file to remember decisions between passes instead of keeping the whole paper and whole note in context.
- To fix one missing piece, patch the specific JSON field, section file, code ref, or figure entry.

Token efficiency is not permission to skip unread sections. Before marking a paper section as brief or omitted, read enough of that section to know what it contains. If a long paper forces a depth tradeoff, state the tradeoff explicitly instead of silently deciding that one chapter is "secondary."

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

This section defines the `analysis.json` contract. Keep the note narrative-first; the schema supports the story.

**Exact item keys.** `assemble.py --check` validates these names:

| Field | Container | Each item's keys |
|---|---|---|
| `qa` | list | `{"q", "a", "type"}` (not `question`/`answer`); `type` in: intuition, principle, detail, limit, engineering, extension |
| `quiz` | list | `{"q", "model_answer"}` (not `question`/`answer`/`a`) |
| `limitations` | list | `{"limit"}` objects (not bare strings); optional `softening` adds an italic counterpoint line |
| `use_cases`, `open_questions` | list | bare strings (not objects) |
| `where_this_matters` | object | `{"items": [{"workload","scale","impact"}, ...]}` (wrap the list in `items`) |
| `related_work` | object | optional `foundational` / `comparable` lists of `{"title","authors","year","why"}`, plus `closest_with_delta` |
| `related_work.closest_with_delta` | object | `{"title", "year", "key_delta"}` (not `delta`) |
| `prerequisites` | list | `{"term", "brief", ...links}` |
| `tech_timeline` | list | `{"year", "label", "delta", "current"}` |
| `paper_figures` | list | `{"src", "caption", "id", "anchor_section", "anchor_phrase"}` |

Do not invent top-level keys. Unknown fields do not render. For example, a method-section intro belongs in the first `method_subsections[]` entry, not a top-level `method_opening` field. For missing table values, write `n/a`.

#### 0. Header Metadata

Required:

- `title`, `authors`, `venue`, `year`
- `subtitle`: one concrete sentence, not a slogan
- `difficulty`: 1-5
- `difficulty_label`: name what is hard, e.g. `matrix calculus`, not `Advanced`
- `estimated_reading_time`: 12-30 min. Don't guess, give reasonable estimate.
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

#### Optional Where this Matters Blocks

Use only when helpful:

- `where_this_matters`: foundational primitives or deployment-facing papers. An object `{"items": [ ... ]}` (the list must be wrapped in `items`, with an optional `intro` string) holding 2-4 concrete workloads. Each item is `{"workload": "...", "scale": "...", "impact": "..."}` (e.g. `{"workload": "Diffusion model personalization", "scale": "10-100 images, single consumer GPU", "impact": "Style adapter ships as a 5-50 MB file"}`). Use when the paper introduces a primitive other systems consume (RoPE, LoRA, attention); skip when the paper is the application.

#### 5. Method subsections (the heart of the note)

This is the heart of the note. Cover the method completely and deeply.

Start from the paper's own method headings. If the paper has `5.1`, `5.1.1`, and `5.1.2`, account for all three. A subsection that looks minor may still carry a definition, assumption, dataset construction step, loss term, training detail, or ablation setup. Cover it briefly if it supports the method.

Organize Core Method like this:

1. **Overall architecture / data flow**
   - Show the architecture figure or a simple Mermaid schematic when the method has multiple moving parts.
   - Explain the data flow from input to output.
   - Name the key modules before diving into formulas.
2. **Core module details**
   - Input and output.
   - Core formula or algorithm, with a prose gloss for every symbol.
   - Pseudocode or code when it helps the reader implement or verify the idea.
   - Design-choice analysis: why this choice beats the obvious alternative, and what tradeoff it introduces.
3. **Key technical details**
   - Training strategy.
   - Hyperparameters.
   - Implementation tricks.
   - Inference tricks.
   - Data preprocessing.
   - Reproduction risks.

Write each substantial method subsection in its own `.html` file and point to it with `body_html_file` (path relative to `analysis.json`). Use inline `body_html` only for tiny sections. This keeps LaTeX, Mermaid, and code easier to edit.

`method_subsections` is a thin index, one entry per algorithm or module:

```json
"method_subsections": [
  {"title": "Plain block (baseline)",               "body_html_file": "sections/01-plain-block.html"},
  {"title": "Residual block (identity + F(x))",     "body_html_file": "sections/02-residual-block.html"},
  {"title": "Bottleneck block (1×1, 3×3, 1×1)",     "body_html_file": "sections/03-bottleneck-block.html"},
  {"title": "Network architecture (ResNet-50/152)", "body_html_file": "sections/04-architecture.html"}
]
```

The long explanation lives in those `.html` files. Keep `analysis.json` as a compact manifest.

Use "Why..." callouts for non-obvious design choices:

```html
<p><strong>Why keep this state instead of recomputing it?</strong> The state is small enough to stay local, while recomputing would scan the full input again. The tradeoff is extra update arithmetic per element.</p>
```

Good "Why..." questions name the design choice, compare it with the obvious alternative, and explain the tradeoff. Use them when they sharpen the explanation.

Use code when the paper defines an algorithm, recurrence, kernel, or implementation detail. A short runnable Python demo with an `assert` is useful when it clarifies the idea. Do not force code into prose-only sections. Put longer code examples in `coderefs.json` as `source: llm_generated` and anchor them from the prose.

A full worked module deep-dive (Multi-Head Self-Attention: architecture diagram → I/O → named formula blocks → code → design analysis) is in `references/method-example.md`. Read it when authoring the first method section.

#### 6. Experiments and Results

Schema:

```json
"experiments_setup_summary": "...",
"main_results": {
  "headline": "...",
  "findings": ["...", "..."],
  "tables": [
    {"caption": "Table 2 - WMT 2014 BLEU vs training cost", "headers": [...], "rows": [...], "highlight_row": 0},
    {"caption": "Table 3 - architecture ablations (dev set)",  "headers": [...], "rows": [...]}
  ],
  "ablations": ["..."]
}
```

(`table` singular is still accepted for a one-table paper; use `tables` when the paper reports several, e.g. main result + ablation grid + transfer.)

This section is analysis, not a number dump. State the conclusions first, then use tables and figures as evidence. Use only the result types the paper actually reports:

- **Main result** (`headline`): the result envelope in one sentence: workload, baseline, metric, magnitude, and the regime where it holds. State the finding, not just the number ("beats the best ensemble by >2 BLEU at ~100x less training cost", not "got 28.4").
- **Findings** (`findings`, 2-5 bullets): one claim per bullet, with the evidence that supports it.
  - *Main comparison*: what the headline number means against the baseline.
  - *Ablation / component attribution*: which mechanism earned which gain (tie each to a row: "single head costs 0.9 BLEU; too many heads also hurts -> there is a sweet spot").
  - *Scaling / efficiency*: the compute-vs-quality relationship, if the paper reports one (FLOPs, params, steps, wall-clock).
  - *Transfer / generalization*: results on a second task or out-of-domain setting, if any.
- **Tables** (`tables`): one captioned table per result family the paper reports; compare regimes, do not dump every number. Highlight the paper's own model row.
- **Ablations** (`ablations`): finer-grained per-component notes that did not rise to a headline finding.
- **Result figures**: include only when the shape of a curve carries the point.
- **Honest read**: if the evaluation is narrow (few tasks, one domain, no scaling study), say so here in a finding; keep method-level weaknesses in the Limitations section, do not duplicate.

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

This is one decision matrix, not another results table. The table holds the axes; the `note` gives the takeaway.

- Pick axes the reader would actually weigh: cost, latency, memory, path length, data needed, or parallelism.
- Include a column that names this paper's delta, so the contrast is explicit.
- `highlight_row` marks this paper's method.
- The `note` is the takeaway, not a caption. State when each method wins and where this paper's method stops winning.
- Use `methods_comparison` for contrasting mechanisms on shared axes; use `related_work` for lineage and prose. Do not duplicate one in the other.

`related_work` renders up to three sub-blocks; each is shown only when its field is populated, so omit ones you cannot fill rather than leaving them empty:

- `foundational`: list of `{"title", "authors", "year", "why"}` for prior work this paper builds on.
- `comparable`: list of `{"title", "authors", "year", "why"}` for parallel alternatives it is measured against.
- `closest_with_delta`: the single closest prior, `{"title": "...", "year": ..., "key_delta": "..."}` (the field is `key_delta`, not `delta`). The key delta should be precise enough that a reader can explain why this paper was still needed.

#### 8. Limitations, Use Cases, Open Questions

3-5 items each. `limitations` are `{"limit": "..."}` objects, each with an optional `softening` string that renders as an italic counterpoint (where the limitation is mitigated, or how later work resolved it); `use_cases` and `open_questions` are bare strings.

- Limitations: assumptions, missing experiments, regimes where the method loses.
- Use cases: concrete places to apply the idea.
- Open questions: what remains unsettled.

Do not duplicate the Q&A. Lists are for scan value; Q&A is for deeper reasoning.

#### 9. Q&A

Q&A is the reader's self-check. Write 5-8 questions across several angles and difficulty levels. Include a question only if a reader who studied the note would still pause on it. Skip rhetorical recaps like "What is the main idea?" and anything the body already answers.

Each item is `{"q": "...", "a": "...", "type": "..."}` (keys `q`/`a`, not `question`/`answer`). Types accepted by renderer:

- `intuition` (0-1): easy gut-check. "In one line, why does this work?"
- `principle` (1-2): design rationale. "Why this choice instead of the obvious alternative?"
- `detail` (1-2): mechanical clarity. "What does this symbol, step, or module actually do?"
- `limit` (0-1): failure condition. "When does this break?"
- `engineering` (1-2): performance envelope. "How does the gain scale, what does it cost, and where does it stop winning?"
- `extension` (0-1): transfer. "Where else could this idea apply, and what would need to change?"

Answer rules:

- Do not fabricate. If the paper does not settle an answer, say what it shows and where the evidence stops.
- Show, don't assert. Use a worked example, a few lines of code, napkin math, or paper numbers when that makes the answer click.
- Mix difficulty. Readers need a few easy intuition wins, not only deep questions.
- For engineering questions, probe scaling and tradeoffs: input size, hardware, memory, latency, accuracy, extra FLOPs, or where another method wins.
- Use numbered lists when an answer has multiple reasons, conditions, or steps.

**Engineering questions.** Probe the *performance envelope* or tradeoffs: how the gain scales with input dimensions and hardware, where it stops winning and what beats it there, and what's traded away to get it (extra flops for fewer memory ops, memory for speed, accuracy for latency). For example:

```text
Q (engineering): "LoRA quality depends on rank r. What sets the right r,
   and where does increasing r stop paying off?"

A: The paper sweeps r ∈ {1, 2, 4, 8, 16, 64} on GPT-3 175B:
   1. Task difficulty — simple classification (RTE, BoolQ) saturates at r=1–2;
      complex generation (E2E NLG) needs r=4–8 to match full finetuning.
   2. Subspace coverage — the top few singular directions of ΔW carry most
      of the task signal, so most tasks need only a few directions.
   3. Cost ceiling — r doesn't change inference latency (A,B are merged at deploy),
      so the only knob is finetune memory; r=8 trains ~9,000× fewer params
      than full finetuning of 175B.
   Takeaway: start at r=4 for general tasks; sweep up only if validation
   loss stays above the full-finetune line.
```

**Answer structure: enumerated lists over walls of prose.** When an answer has multiple reasons, conditions, or steps, name and number them:

> Bad: "In Stage 4 because if you introduced synthetic data earlier the model wouldn't have built up visual priors and pure-color-background-plus-text lacks natural textures so it would interfere with the fit and also caption quality depends on the VLM…"
>
> Good: "Introducing synthetic data before Stage 4 has **two risks**:
> 1. **Visual priors aren't established yet** - synthetic text images lack natural-scene textures; introducing them early distorts the model's fit to real image statistics.
> 2. **Caption quality depends on model strength** - captioning synthetic scenes needs a strong enough VLM; Stage 4 is the earliest point that's reliable.
> This 'natural-image foundation first, specialized data later' curriculum mirrors pretrain-then-finetune."

#### 10. Quiz

3-5 self-check items, each `{"q": "...", "model_answer": "..."}` (note `model_answer`, not `a`/`answer`). Ask the reader to derive, compare, or sketch. Multi-line code answers must use markdown fences.

#### Figures

`paper_figures` entries:

```json
{
  "id": "model-architecture",
  "src": "p05_raster_00.png",
  "caption": "Figure 1 - Transformer model architecture. <strong>Shows</strong>: encoder and decoder stacks with multi-head attention, feed-forward layers, residual connections, and normalization. <strong>From paper</strong>: §3.",
  "anchor_section": "architecture"
}
```

Schema rules (`--check` enforces the first two):

- Caption must include `<strong>Shows</strong>` (what the image depicts) and `<strong>From paper</strong>` (the source section/figure).
- `anchor_section` is one of: `header`, `overview`, `motivation`, `architecture`, `method`, `experiments`, `comparison`, `related`, `limits`, `inline`.
- The paper's **overall-architecture figure** uses `anchor_section: "architecture"` (no `anchor_phrase`); it is hoisted to open Core Method. The introduction should establish problem, background, and the paper's move before showing implementation structure.
- A method figure takes an `anchor_phrase` (verbatim prose from the target section) that positions it before that paragraph; omit `anchor_phrase` only for the `architecture` figure.

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

Build a short coverage plan before authoring. It prevents dropped sections. For long or multi-pass papers, save it to `/tmp/yomitoki/<paper-slug>/coverage.md`.

Plan in two passes:

1. **Inventory.** List every paper section/subsection in order. Read the local text for each heading before deciding its coverage. Mark each as cover deeply, cover briefly, or omit, with a short reason. A heading with its own formula, algorithm, module, result, dataset step, training detail, or assumption usually deserves coverage. Minor but valid subsections should become a brief paragraph, table row, or named note rather than disappearing.
2. **Spine.** Write five lines: Problem / Old way / Failure mode / Paper's move / Payoff. Use this to order and weight the note.

The plan (inline, or `coverage.md` for long papers) holds the spine plus these tables:

```text
Spine: Problem / Old way / Failure mode / Paper's move / Payoff

Contribution inventory: | Paper heading (in order) | Stated contribution? | Cover deeply/briefly/omit | Note section | Evidence |
Method section plan:     | Section file | Headings covered | Paper evidence | Code/diagram need |
Experiment map:          | Claim | Metric / dataset / baseline | Paper table/figure | Note placement |
Figure candidates:       | Figure | Type (arch/method/result/ablation/compare) | Keep? | Anchor section |
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

Use the method-section guidance above while writing each file. `references/method-example.md` is the full worked example.

- Open the method with an architecture / data-flow map (a paper figure or Mermaid) when the paper has more than one moving part; skip it for a single small mechanism.
- The bar is content, not layout. A single-mechanism paper can use flowing prose, but it still needs inputs, outputs, symbols, and the reason the design works.

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

Pick figures that teach the paragraph where they appear or carry result evidence. Do not add a diagram just because a section feels empty. If the paper has no architecture figure, use a Mermaid schematic only when the architecture or flow is clear from the paper. Place method figures near the prose they explain with `anchor_phrase`.

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

Author from this skill's contract and let `--check` report structural problems.

Fix hard failures. Review warnings and revise when they point to a real issue.

### 8. Final Self-Review

Before calling the note done, read the TL;DR, Overview, and first method subsection as a reader. Ask:

- Can the reader explain the problem and the fix in five minutes?
- Does the contrast with prior methods appear before implementation detail?
- Are the strongest numbers tied to the regime where they apply?
- Are code refs real and line-specific when a repo exists?
- Did any section become a checklist rather than an explanation?

Then run a coverage pass. Walk the paper's headings in order and confirm each covered heading appears in the note. A heading with its own formula, algorithm, module, or result should not disappear into a background sentence. If a stated contribution is absent, add it before shipping. `assemble.py --check` validates structure, not coverage.

If the answer is no, revise the prose first. The checker cannot judge taste.

## Reference Files

- `references/code-ref-waterfall.md`: code reference sourcing, line anchors, snippets.
- `references/diagrams.md`: figure curation and Mermaid safety.
- `references/method-example.md`: full worked module deep-dive (read when authoring the first method section).
- `scripts/extract.py`: paper extraction.
- `scripts/assemble.py`: HTML rendering and validation.
