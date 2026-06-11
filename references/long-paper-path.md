# Long-paper path

For a long paper, do not keep the whole paper, every draft, and all the code in
context at once. Two roles:

- **Main agent**: does the understanding. Reads the core method, writes the sections
  that connect to each other, owns `analysis.json` and the final read-through.
- **Subagent (helper)**: does one small, well-defined job in its own context and
  returns only the result. Two jobs: look up facts, or write up a self-contained
  section from a detailed plan.

Rule: hand a step to a helper only if it needs no judgment that depends on the rest
of the paper.

## Split work by kind, not by section

| Kind of work | Who | Why |
|---|---|---|
| Understand the paper (main idea, how parts fit, why each choice) | Main agent, directly | This is the thread that ties the note together; delegating it produces glued-together summaries. |
| Look things up (code line numbers, settings, result numbers, figure details, facts from minor sections) | Helpers | Pure lookup; a short summary loses nothing. |
| Write up a self-contained section (a filled-in plan -> finished HTML/KaTeX/code) | Helpers | Safe only when the plan already contains all the thinking. |

You do not save tokens by understanding less. You save them by not keeping raw paper
text in context after you have understood it: read the method, distill into
`coverage.md`, then let the raw text drop out.

## Phases

**0. Sort the sections (main agent).** After extract, skim the TOC, headings, figure
captions, and contribution list. Mark each section "read closely myself" (core
method) or "helper pulls facts" (result tables, appendix, related work).

**1. Understand the core (main agent, read in full).** Write the spine and main
thread into `coverage.md`. For each planned section, note which other sections it
refers back to or sets up (its `coherence_links`). That decides who writes it:
- **Key section, main agent writes it**: connects to another method section, or holds
  the paper's central contribution.
- **Hand-off section, a helper writes it**: connects only to the overview / shared
  `coverage.md`.
Then distill the method text into `coverage.md` and release the raw text.

**2. Look things up in parallel (helpers).** Send helpers out for facts, not
judgment. Return formats below.

**3. Write the sections.** Main agent writes `analysis.json` and every key section
(one at a time, opening only `coverage.md` + the excerpt). For each hand-off section,
send one helper a full section plan (schema below); the helper turns it into the
section HTML and must not invent mechanism.

**4. Assemble and read through (main agent).** Run `assemble.py --check`, then do the
three checks and the flow read below. This step is essential, not polish.

## Section plan (a helper's input for a hand-off section)

Field names are JSON keys the helper reads. Example uses a textbook topic so the
schema stays paper-agnostic.

```json
{
  "title": "Scaled dot-product attention",
  "io": {"input": "Q, K, V in R^{n x d}", "output": "context in R^{n x d}"},
  "formulas": [
    {"latex": "\\text{Attn}(Q,K,V) = \\text{softmax}\\!\\left(\\frac{QK^\\top}{\\sqrt{d}}\\right)V",
     "gloss": [{"sym": "QK^\\top", "meaning": "pairwise query-key similarity"},
               {"sym": "\\sqrt{d}", "meaning": "scaling that keeps logit variance ~1"}],
     "key_point": "softmax row-normalizes over keys, so each query gets a convex mix of values"}
  ],
  "why_callouts": [
    {"question": "Why divide by sqrt(d)?",
     "obvious_alternative": "use the raw dot product",
     "answer": "logits grow with d and push softmax into a near one-hot, vanishing-gradient regime",
     "tradeoff": "one extra scalar multiply per logit"}
  ],
  "code_demo": {"computes": "the attention forward pass", "invariant_to_assert": "rows of softmax sum to 1", "approx_lines": 10},
  "coherence_links": [{"to_section": "multi-head", "phrasing": "this is the per-head operation multi-head runs h times"}],
  "anchor_phrases": ["scores every query against every key"],
  "prose_arc": "open with similarity-then-mix intuition; give the formula; explain the scaling; close by handing off to multi-head",
  "excerpt": "<the exact paper text for this section>",
  "style_ref": "follow references/method-example.md; KaTeX for all math; no em-dashes"
}
```

Field meanings:
- `title` / `io` — heading; what goes in and out.
- `formulas` — each equation, every symbol's meaning, and the one takeaway. Main agent writes these.
- `why_callouts` — the "Why did they do it this way?" boxes, **answer already written by the main agent**. The helper adds none of its own.
- `code_demo` — what the small example computes and what its `assert` checks.
- `coherence_links` — which other sections to reference, and how to phrase it.
- `anchor_phrases` — sentences that must appear word-for-word (see below).
- `prose_arc` — the order to tell the section in.
- `excerpt` — the exact paper text.
- `style_ref` — formatting rules.

The main agent writes everything that carries meaning (formulas, why-answers,
cross-references). The helper renders; it does not decide.

`anchor_phrases`: the note's side-panel cards (code snippets, figures) each hook to
an exact sentence. If a helper rewords that sentence, the card breaks and `--check`
fails. The main agent copies those exact sentences here from `coderefs.json` (and
figure entries) before dispatch; pass `[]` if none. Helper instruction: "Include
each string in `anchor_phrases` word-for-word, once, in a natural sentence; do not
reword."

Add to every typeset helper's instructions: "Use only the `why_callouts` in the
plan. Do not add your own. If the text suggests a reason the plan omits, report it
back instead of writing it." (Tested: without this, helpers invent Why-boxes.)

## Fact-finding return formats (Phase 2)

```json
{"code_refs":   [{"concept": "", "file": "", "line_start": 0, "line_end": 0, "preview_5_lines": ""}],
 "result_table":{"headers": [], "rows": []},
 "figures":     [{"fig_id": "", "page": 0, "caption": "", "teaches": "", "keep": true, "anchor_section": ""}],
 "peripheral":  {"claims": [], "numbers": []}}
```

## Phase 4 checklist

Three checks first (each one is here because a test caught it):

- **A. Fix broken links.** `--check` fails when a code/figure card's sentence was
  reworded. Restore the exact sentence (preferred; it was an `anchor_phrases` entry)
  or update the anchor in `coderefs.json` / the figure entry. Re-run until green.
- **B. Check every helper code demo.** Run each one; confirm the `assert` tests a real
  invariant, not something trivially true or faked. Rewrite weak ones. Helper code
  regresses more often than helper prose.
- **C. Strip and trim.** Remove any stray opening line a helper added ("Here is the
  section body."). Helper sections trend ~15-25% long; trim to the density of the
  main-agent sections so the note reads in one voice.

Then read for flow:
1. One voice across all sections?
2. Each cross-reference actually appears and points somewhere real?
3. No two sections re-explaining the same thing?
4. Can you state the one main point the note is built around?
5. Same symbol/name for the same thing throughout?

## Optional Workflow script (Phases 2-3 only)

Phases 0/1/4 stay with the main agent. A Workflow script can run the mechanical
fan-out: a `Retrieve` phase (helpers return the fact formats above) then a `Typeset`
phase (one helper per hand-off section, each writing `sections/<file>.html` from its
plan). Key sections and `analysis.json` stay out of the script so the main thread
lives in one head.
