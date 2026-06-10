#!/usr/bin/env python3
"""
assemble.py — Yomitoki HTML reader assembler

Takes analysis.json + coderefs.json + figures + assets and produces
a self-contained HTML reader in --out with the 13-block structure.

Usage:
    python assemble.py \
        --analysis /path/to/analysis.json \
        --coderefs /path/to/coderefs.json \
        --figures  /path/to/figures/ \
        --assets   /path/to/assets/ \
        --out      /path/to/output-dir/
"""

import argparse
import html as html_lib
import json
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(s):
    """HTML-escape a plain string."""
    if s is None:
        return ""
    return html_lib.escape(str(s))


_INLINE_ALLOWED = ("strong", "em", "code", "b", "i")
_INLINE_TAG_RE = re.compile(
    r"&lt;(/?)(" + "|".join(_INLINE_ALLOWED) + r")&gt;",
    re.IGNORECASE,
)


def esc_inline(s):
    """HTML-escape, then re-allow a tiny inline allowlist (<strong> <em> <code> <b> <i>).

    Lets short fields (like Main Contributions bullets) include a bit of inline
    emphasis without opening the door to arbitrary HTML.
    """
    if s is None:
        return ""
    escaped = html_lib.escape(str(s))
    return _INLINE_TAG_RE.sub(lambda m: f"<{m.group(1)}{m.group(2).lower()}>", escaped)


_FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


def esc_answer(s):
    """Render a Q&A / quiz answer.

    Supports markdown-style code fences (```lang ... ```) → <pre class="code-snippet">.
    Single newlines outside fences become <br> so multi-line prose stays readable.
    Inline allowlist (esc_inline) applies to the prose portions.
    """
    if s is None:
        return ""
    text = str(s)
    parts = []
    last = 0
    for m in _FENCE_RE.finditer(text):
        prose = text[last:m.start()]
        if prose:
            parts.append(esc_inline(prose).replace("\n", "<br>\n"))
        code = m.group(2).rstrip("\n")
        parts.append(
            f'<pre class="code-snippet"><code>{html_lib.escape(code)}</code></pre>'
        )
        last = m.end()
    tail = text[last:]
    if tail:
        parts.append(esc_inline(tail).replace("\n", "<br>\n"))
    return "".join(parts)


def stars(n):
    return "⭐" * int(n)


# ---------------------------------------------------------------------------
# Jargon wrapping (BeautifulSoup pass)
# ---------------------------------------------------------------------------

_MATH_DELIM_RE = re.compile(r"\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$", re.DOTALL)


def _find_outside_math(text: str, term: str) -> int:
    """First index of `term` not inside a KaTeX math span (\\[...\\], \\(...\\),
    $$...$$); -1 if none. Wrapping a term inside an equation would split the
    \\[...\\] delimiters and stop KaTeX from rendering that equation."""
    spans = [(m.start(), m.end()) for m in _MATH_DELIM_RE.finditer(text)]
    start = 0
    while True:
        idx = text.find(term, start)
        if idx == -1:
            return -1
        if not any(s < idx + len(term) and idx < e for s, e in spans):
            return idx
        start = idx + 1


def _wrap_jargon(html_str: str, jargon: dict) -> str:
    """
    For each term in jargon dict, wrap the FIRST occurrence (case-sensitive)
    in <span class="jargon" data-gloss="...">{term}</span>.
    Skips occurrences inside <aside class="explain">, <pre>, or <code>.
    Uses BeautifulSoup for safe HTML manipulation.
    """
    if not jargon or not html_str.strip():
        return html_str

    try:
        from bs4 import BeautifulSoup, NavigableString
    except ImportError:
        # bs4 not available — return unchanged
        return html_str

    soup = BeautifulSoup(html_str, "html.parser")

    for term, gloss in jargon.items():
        gloss_escaped = gloss.replace('"', "&quot;")
        found = False

        # Walk all text nodes
        for text_node in soup.find_all(string=True):
            if found:
                break

            # Skip if inside aside.explain, pre, or code
            parent = text_node.parent
            skip = False
            for ancestor in [parent] + list(parent.parents):
                tag = getattr(ancestor, "name", None)
                if tag in ("pre", "code"):
                    skip = True
                    break
                if tag == "aside" and ancestor.get("class") and "explain" in ancestor.get("class", []):
                    skip = True
                    break
            if skip:
                continue

            # Check if term appears in this text node
            text = str(text_node)
            if term not in text:
                continue

            # Replace first occurrence that is NOT inside a KaTeX math span
            idx = _find_outside_math(text, term)
            if idx == -1:
                continue
            before = text[:idx]
            after = text[idx + len(term):]

            # Build replacement: before + span + after
            span_html = (
                f'<span class="jargon" data-gloss="{gloss_escaped}">'
                f"{html_lib.escape(term)}</span>"
            )
            new_node = BeautifulSoup(
                html_lib.escape(before) + span_html + html_lib.escape(after),
                "html.parser",
            )
            text_node.replace_with(new_node)
            found = True

    return str(soup)


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def build_head(a: dict) -> str:
    title_safe = esc(a.get("title", "Paper Reader"))
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_safe} — Yomitoki</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <!-- styles.css loads LAST so our overrides (e.g. .katex font-size pinning)
       beat the KaTeX CDN's default `.katex {{ font-size: 1.21em }}`. -->
  <link rel="stylesheet" href="styles.css">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{
      delimiters: [
        {{left: '\\\\[', right: '\\\\]', display: true}},
        {{left: '$$', right: '$$', display: true}},
        {{left: '\\\\(', right: '\\\\)', display: false}}
      ],
      throwOnError: false
    }});"></script>
</head>
<body>"""


def build_block1_header(a: dict) -> str:
    """Block 1 — Header."""
    paper_url = esc(a.get("paper_url", "#"))
    author_repo = a.get("author_repo")
    arxiv_url = a.get("arxiv_url")

    meta_links = [f'<a href="{paper_url}" target="_blank" rel="noopener">PDF</a>']
    if author_repo:
        meta_links.append(f'<a href="{esc(author_repo)}" target="_blank" rel="noopener">Code</a>')
    if arxiv_url:
        meta_links.append(f'<a href="{esc(arxiv_url)}" target="_blank" rel="noopener">arXiv</a>')

    meta_links_str = " | ".join(meta_links)

    title = esc(a.get("title", ""))
    subtitle = a.get("subtitle")
    authors = esc(a.get("authors", ""))
    venue = esc(a.get("venue", ""))
    year = esc(str(a.get("year", "")))
    difficulty = int(a.get("difficulty", 3))
    difficulty_label = esc(a.get("difficulty_label", ""))
    reading_time = a.get("estimated_reading_time")
    reading_time_html = (
        f'<span class="reading-time">📖 {esc(reading_time)}</span>'
        if reading_time else ""
    )

    tags_html = "".join(
        f'<span class="tag">{esc(t)}</span>' for t in a.get("tags", [])
    )

    # Header figures (anchor_section == "header")
    header_figs_html = ""
    for fig in a.get("paper_figures", []):
        if fig.get("anchor_section") == "header":
            header_figs_html += _figure_html(fig)

    subtitle_html = f"\n    <p class=\"subtitle\">{esc(subtitle)}</p>" if subtitle else ""

    return f"""
  <!-- ══ BLOCK 1 — HEADER ══════════════════════════════════════════════════ -->
  <header class="paper-header">
    <p class="meta-top">
      Yomitoki |
      {meta_links_str}
    </p>
    <h1>{title}</h1>{subtitle_html}
    <p class="authors">{authors}</p>
    <p class="venue-line">
      {venue} | {year}
      <span class="difficulty" title="{difficulty_label}">{stars(difficulty)}</span>
      <span class="difficulty-label">{difficulty_label}</span>
      {reading_time_html}
    </p>
    <p class="tags">
      {tags_html}
    </p>
    {header_figs_html}
  </header>"""


def build_block2_prereqs(a: dict) -> str:
    """Block 2 — Prerequisites strip."""
    prereqs = a.get("prerequisites", [])
    if not prereqs:
        return ""

    items = []
    for p in prereqs:
        term = esc(p.get("term", ""))
        brief = esc(p.get("brief", ""))
        primary_link = esc(p.get("primary_link", "#"))
        primary_title = esc(p.get("primary_title", "link"))
        beginner_link = p.get("beginner_link")
        beginner_title = p.get("beginner_title")

        beginner_html = ""
        if beginner_link:
            beginner_html = (
                f'\n            <a href="{esc(beginner_link)}" target="_blank" rel="noopener">'
                f'{esc(beginner_title)}</a>'
            )

        items.append(f"""\
      <details class="prereq">
        <summary class="prereq-pill">{term}</summary>
        <div class="prereq-detail">
          <p>{brief}</p>
          <p class="prereq-links">
            <a href="{primary_link}" target="_blank" rel="noopener">{primary_title}</a>{beginner_html}
          </p>
        </div>
      </details>""")

    items_str = "\n\n".join(items)
    return f"""
  <!-- ══ BLOCK 2 — PREREQUISITES ══════════════════════════════════════════ -->
  <section class="prereqs">
    <p class="label">Prerequisites · brush up before reading</p>
    <div class="prereq-list">

{items_str}

    </div>
  </section>"""


def build_block3_tldr(a: dict) -> str:
    """Block 3 — TL;DR card: one flowing paragraph (~2-3 sentences), structured
    problem → technique → performance, rendered with no row labels.
    """
    summary = a.get("tldr", {}).get("summary", "").strip()

    return f"""
    <!-- ══ BLOCK 3 — TL;DR ════════════════════════════════════════════════════ -->
    <section id="tldr" class="tldr">
      <p class="label">TL;DR</p>
      <p class="tldr-summary">{esc_inline(summary)}</p>
    </section>"""


def build_block3b_overview(a: dict) -> str:
    """Block 3b — Paper Overview + Background (combined).

    Renders as one section with two layers:
      1. Quick-answer cards (problem / solution / contributions) from `paper_overview`
      2. Background prose (existing methods, bottlenecks, root cause) from
         `paper_overview.background`

    Either layer can be absent; section is skipped only if both are missing.
    """
    ov = a.get("paper_overview") or {}
    background = ov.get("background", "")

    problem = ov.get("problem", "")
    solution = ov.get("solution", "")
    contributions = ov.get("contributions", [])

    def _para(text: str) -> str:
        if text.lstrip().startswith("<"):
            return text
        return f"<p>{esc_inline(text)}</p>"

    # --- Layer 1: quick-answer cards ---
    contrib_html = ""
    if contributions:
        items = "".join(f"\n          <li>{esc_inline(c)}</li>" for c in contributions)
        contrib_html = f"""
      <div class="overview-card overview-contributions">
        <p class="label">Main Contributions</p>
        <ul>{items}
        </ul>
      </div>"""

    problem_html = f"""
      <div class="overview-card overview-problem">
        <p class="label">Problem</p>
        {_para(problem)}
      </div>""" if problem else ""

    solution_html = f"""
      <div class="overview-card overview-solution">
        <p class="label">Solution</p>
        {_para(solution)}
      </div>""" if solution else ""

    # Wrap the standalone Problem card so it spans the full width above the
    # Background prose. The Solution + Contributions cards stay together as
    # a 2-up grid below the Background, giving the section a narrative flow:
    # Problem (motivation) → Background (why prior methods fail) → Offering
    # (Solution + Contributions, the answer).
    problem_block_html = ""
    if problem_html:
        problem_block_html = f"""
      <div class="overview-problem-block">{problem_html}
      </div>"""

    offering_html = ""
    if solution_html or contrib_html:
        offering_html = f"""
      <div class="overview-offering">{solution_html}{contrib_html}
      </div>"""

    # --- Background prose (sits between Problem and Offering) ---
    motivation_body = ""
    if isinstance(background, str) and background.strip():
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", background) if p.strip()]
        motivation_body = "\n        ".join(
            f"<p>{esc_inline(p)}</p>" for p in paragraphs
        )
    elif isinstance(background, dict) and background.get("body_html"):
        motivation_body = background["body_html"]
    elif isinstance(background, list) and background:
        items_html = "".join(
            f"\n          <li>{esc_inline(step)}</li>" for step in background
        )
        motivation_body = f'<ol class="motivation-chain">{items_html}\n        </ol>'

    fig_html = _anchor_figs_html(a, "overview") + _anchor_figs_html(a, "motivation")

    motivation_html = ""
    if motivation_body:
        motivation_html = f"""
      <div class="overview-background">
        <p class="label">Background</p>
        {motivation_body}
      </div>"""

    # Skip the whole section if nothing to show
    if not problem_block_html and not motivation_html and not offering_html:
        return ""

    return f"""
    <!-- ══ BLOCK 3b — PAPER OVERVIEW (Problem → Background → Offering) ════ -->
    <section id="overview" class="overview">
      <h2>Paper Overview</h2>{fig_html}{problem_block_html}{motivation_html}{offering_html}
    </section>"""


def build_block5_timeline(a: dict) -> str:
    """Block 5 — Tech Evolution Timeline (custom CSS, not Mermaid).

    Mermaid auto-shrinks text when there are many nodes, making the timeline
    unreadable. A custom flex/grid layout gives consistent typography and
    wraps to a second row if needed.
    """
    nodes = a.get("tech_timeline", [])
    if not nodes:
        return ""

    # Detect which node represents "this work": explicit `current: true` flag,
    # or the first node whose label contains "(this work)" / "this paper" /
    # "(ours)". Fall back to the last node.
    last_idx = len(nodes) - 1
    current_idx = None
    for i, node in enumerate(nodes):
        if node.get("current") is True:
            current_idx = i
            break
    if current_idx is None:
        for i, node in enumerate(nodes):
            label_l = (node.get("label", "") + " " + node.get("delta", "")).lower()
            if "(this work)" in label_l or "(this paper)" in label_l or "(ours)" in label_l or "this paper" in label_l:
                current_idx = i
                break
    if current_idx is None:
        current_idx = last_idx

    items_html = ""
    for i, node in enumerate(nodes):
        yr = esc(str(node.get("year", "")))
        label = esc(node.get("label", ""))
        delta = esc(node.get("delta", ""))
        is_current = " timeline-node-current" if i == current_idx else ""
        items_html += f"""
        <div class="timeline-node{is_current}">
          <div class="timeline-year">{yr}</div>
          <div class="timeline-label">{label}</div>
          <div class="timeline-delta">{delta}</div>
        </div>"""
        if i != last_idx:
            items_html += '<div class="timeline-arrow" aria-hidden="true">→</div>'

    if current_idx == last_idx:
        caption = "Key milestones leading to this paper. The most recent node is this work."
    elif current_idx == 0:
        caption = "This work is the earliest highlighted node; later nodes are downstream follow-ups."
    else:
        caption = "This work is highlighted; earlier nodes are prerequisites, later nodes are downstream consumers / follow-ups."

    return f"""
    <!-- ══ BLOCK 5 — TECH TIMELINE (custom CSS) ════════════════════════════ -->
    <section id="timeline" class="paper-section">
      <h2>Tech Timeline</h2>
      <div class="tech-timeline">{items_html}
      </div>
      <p class="timeline-caption">{caption}</p>
    </section>"""


def _figure_html(fig: dict, extra_class: str = "") -> str:
    """Render a single paper figure as <figure> HTML.

    The caption preserves a small inline allowlist (<strong>/<em>/<code>/<b>/<i>)
    via esc_inline; the alt attribute strips those tags and any math delimiters
    to plain text so screen readers don't read raw markup.
    """
    raw_caption = fig.get("caption", "") or ""
    src = esc(fig.get("src", ""))
    fig_id = esc(fig.get("id", ""))
    caption = esc_inline(raw_caption)
    # Build a plain-text alt: drop inline tags and KaTeX delimiters.
    alt_text = re.sub(r"</?(?:strong|em|code|b|i)>", "", raw_caption, flags=re.IGNORECASE)
    alt_text = re.sub(r"\\\[|\\\]|\\\(|\\\)|\$\$", "", alt_text)
    alt = esc(alt_text.strip()) or fig_id
    cls = f'paper-figure{" " + extra_class if extra_class else ""}'
    return f"""
      <figure class="{cls}" id="fig-{fig_id}">
        <img src="figures/{src}" alt="{alt}" loading="lazy">
        <figcaption>{caption}</figcaption>
      </figure>"""


def _anchor_figs_html(a: dict, section_id: str) -> str:
    """Collect figures whose anchor_section matches section_id."""
    out = ""
    for fig in a.get("paper_figures", []):
        if fig.get("anchor_section") == section_id:
            out += _figure_html(fig)
    return out


def build_block5b_where_this_matters(a: dict) -> str:
    """Block 5b — Where this matters (OPTIONAL).

    Bridges the historical timeline to the method by showing concretely
    where the paper's technique runs in real systems / workloads. Skipped
    entirely if `where_this_matters` is missing.

    Schema:
        "where_this_matters": {
          "intro": "string — one paragraph framing where this technique lands",
          "items": [
            {"workload": "...", "scale": "...", "impact": "..."},
            ...
          ]
        }
    """
    wtm = a.get("where_this_matters")
    if not wtm:
        return ""
    intro = wtm.get("intro", "")
    items = wtm.get("items", [])
    if not intro and not items:
        return ""

    intro_html = f"<p class=\"section-intro\">{esc_inline(intro)}</p>" if intro else ""

    rows_html = ""
    for it in items:
        workload = esc_inline(it.get("workload", ""))
        scale    = esc_inline(it.get("scale", ""))
        impact   = esc_inline(it.get("impact", ""))
        rows_html += (
            f"<tr><td><strong>{workload}</strong></td>"
            f"<td>{scale}</td><td>{impact}</td></tr>"
        )

    table_html = ""
    if rows_html:
        table_html = (
            "<table>"
            "<thead><tr><th>Workload</th><th>Scale</th><th>Impact</th></tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
        )

    return f"""
    <!-- ══ BLOCK 5b — WHERE THIS MATTERS (optional) ════════════════════════ -->
    <section id="context" class="paper-section where-matters">
      <h2>Where this matters</h2>
      {intro_html}
      {table_html}
    </section>"""


def _mark_why_callouts(body_html: str) -> str:
    """Tag every `<p>` whose first <strong> reads "Why …?" with class
    `why-callout`, so styles.css can render it as a boxed callout instead of
    a plain paragraph. The authoring rule keeps the simple `<p><strong>Why X?</strong> …</p>`
    shape — this pass just labels them for the renderer.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(body_html, "html.parser")
    for p in soup.find_all("p"):
        first_tag = p.find(True, recursive=False)
        if first_tag is None or first_tag.name != "strong":
            continue
        text = first_tag.get_text(strip=True)
        if text.startswith("Why") and text.endswith("?"):
            classes = p.get("class") or []
            if isinstance(classes, str):
                classes = classes.split()
            if "why-callout" not in classes:
                classes.append("why-callout")
                p["class"] = classes
    return str(soup)


def _insert_figure_at_phrase(body_html: str, phrase: str, fig_html: str) -> tuple[str, bool]:
    """Insert `fig_html` immediately before the first top-level element whose
    text contains `phrase`. Returns (new_body_html, True) when inserted;
    (body_html, False) otherwise, so the caller can fall back to appending.

    The phrase is matched in element .get_text() (so attributes and HTML
    structure are ignored), and elements nested inside <pre>/<code> are skipped
    so we don't break a code block.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(body_html, "html.parser")
    for el in soup.find_all(["p", "ul", "ol", "table", "h4", "h5", "blockquote"]):
        if phrase in el.get_text() and not el.find_parent(["pre", "code"]):
            fig_node = BeautifulSoup(fig_html, "html.parser")
            el.insert_before(fig_node)
            return str(soup), True
    return body_html, False


def build_block6_method(a: dict) -> str:
    """Block 6 — Core Method.

    Equations are NOT rendered as a separate appendix block. They always live
    inline inside the relevant `method_subsections[].body_html`.
    """
    subsections = a.get("method_subsections", [])
    paper_figures = a.get("paper_figures", [])

    # Overview/architecture figure: a method figure without anchor_phrase, or
    # an explicit id == "architecture". Anchored method figures must stay
    # anchored to the paragraph they explain instead of being hoisted to the
    # top of Core Method.
    arch_fig = None
    for fig in paper_figures:
        if (
            fig.get("anchor_section") == "method"
            and not fig.get("anchor_phrase")
            and arch_fig is None
        ):
            arch_fig = fig
            break
    if arch_fig is None:
        for fig in paper_figures:
            if fig.get("id") == "architecture":
                arch_fig = fig
                break

    arch_html = _figure_html(arch_fig) if arch_fig else ""

    # Figures eligible to flow into the per-subsection bodies: every method-
    # anchored figure that isn't the architecture figure. We track which ones
    # have been placed so each appears exactly once.
    method_figs = [
        fig for fig in paper_figures
        if fig.get("anchor_section") == "method" and fig is not arch_fig
    ]
    placed_fig_ids = set()

    # --- Method subsections ---
    subs_html = ""
    last_subs_idx = len(subsections) - 1
    for sub_idx, sub in enumerate(subsections):
        heading = esc(sub.get("title") or "")
        body_html = sub.get("body_html", "")  # already HTML, don't escape
        body_html = _mark_why_callouts(body_html)
        explainer = sub.get("explainer")

        # Figure placement: for each unplaced method figure with an anchor_phrase,
        # try to insert it *before* the matching prose element in THIS subsection.
        # If the phrase doesn't match here, leave the figure for a later subsection.
        # Figures still unplaced after all subsections are appended once at the
        # end of the last subsection (fallback), never duplicated.
        fig_html = ""
        for fig in method_figs:
            fid = id(fig)
            if fid in placed_fig_ids:
                continue
            phrase = fig.get("anchor_phrase")
            if phrase:
                body_html, inserted = _insert_figure_at_phrase(
                    body_html, phrase, _figure_html(fig)
                )
                if inserted:
                    placed_fig_ids.add(fid)
            elif sub_idx == last_subs_idx:
                # No anchor phrase: append once at the end of the last subsection.
                fig_html += _figure_html(fig)
                placed_fig_ids.add(fid)

        # On the last subsection, append any figures that still didn't find an
        # anchor phrase anywhere in the body.
        if sub_idx == last_subs_idx:
            for fig in method_figs:
                fid = id(fig)
                if fid not in placed_fig_ids:
                    fig_html += _figure_html(fig)
                    placed_fig_ids.add(fid)

        explainer_html = ""
        if explainer:
            explainer_html = f"""
        <aside class="explain"><p>💡 {esc(explainer)}</p></aside>"""

        subs_html += f"""
      <div class="subsection">
        <h3>{heading}</h3>
        {body_html}{fig_html}{explainer_html}
      </div>"""

    # Block ordering inside Core Method:
    #   architecture figure → method_subsections (which carry their own
    #   inline equations in body_html).
    return f"""
    <!-- ══ BLOCK 6 — CORE METHOD ═════════════════════════════════════════════ -->
    <section id="method" class="paper-section">
      <h2>Core Method</h2>
{arch_html}
{subs_html}
    </section>"""


def build_block7_experiments(a: dict) -> str:
    """Block 7 — Experiments."""
    setup = a.get("experiments_setup_summary", "")
    results = a.get("main_results", {})
    headline = esc(results.get("headline", ""))
    table = results.get("table", {})
    ablations = results.get("ablations", [])

    fig_html = _anchor_figs_html(a, "experiments")
    if not setup and not headline and not table.get("headers") and not ablations and not fig_html:
        return ""

    setup_html = f"<p>{esc(setup)}</p>\n" if setup else ""

    # Results table
    headers = table.get("headers", [])
    rows = table.get("rows", [])
    highlight_row = table.get("highlight_row")

    thead_html = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tbody_html = ""
    for i, row in enumerate(rows):
        cls = ' class="highlight"' if i == highlight_row else ""
        cells = "".join(f"<td>{esc(str(cell))}</td>" for cell in row)
        tbody_html += f"\n          <tr{cls}>{cells}</tr>"

    table_html = ""
    if headers:
        table_html = f"""
      <table class="results-table">
        <thead>
          <tr>{thead_html}</tr>
        </thead>
        <tbody>{tbody_html}
        </tbody>
      </table>"""

    ablations_html = ""
    if ablations:
        items = "".join(f"\n        <li>{esc_inline(a_item)}</li>" for a_item in ablations)
        ablations_html = f"""
      <p class="label">Ablation highlights</p>
      <ul class="ablations">{items}
      </ul>"""

    return f"""
    <!-- ══ BLOCK 7 — EXPERIMENTS ════════════════════════════════════════════ -->
    <section id="experiments" class="paper-section">
      <h2>Experiments</h2>
      {setup_html}<p class="results-headline">{headline}</p>{fig_html}
{table_html}
{ablations_html}
    </section>"""


def build_block8_comparison(a: dict) -> str:
    """Block 8 — Methods Comparison."""
    comp = a.get("methods_comparison", {})
    headers = comp.get("headers", [])
    rows = comp.get("rows", [])
    highlight_row = comp.get("highlight_row")
    note = (comp.get("note") or "").strip()
    fig_html = _anchor_figs_html(a, "comparison")

    if not headers and not fig_html and not note:
        return ""

    thead_html = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tbody_html = ""
    for i, row in enumerate(rows):
        cls = ' class="highlight"' if i == highlight_row else ""
        cells = "".join(f"<td>{esc(str(cell))}</td>" for cell in row)
        tbody_html += f"\n          <tr{cls}>{cells}</tr>"

    table_html = ""
    if headers:
        table_html = f"""
      <table class="results-table">
        <thead>
          <tr>{thead_html}</tr>
        </thead>
        <tbody>{tbody_html}
        </tbody>
      </table>"""

    note_html = f'\n      <p class="comparison-note">{esc_inline(note)}</p>' if note else ""

    return f"""
    <!-- ══ BLOCK 8 — METHODS COMPARISON ════════════════════════════════════ -->
    <section id="comparison" class="paper-section">
      <h2>Methods Comparison</h2>{fig_html}
      {table_html}{note_html}
    </section>"""


def build_block9_related(a: dict) -> str:
    """Block 9 — Related Work (3 sub-blocks)."""
    rw = a.get("related_work", {})
    foundational = rw.get("foundational", [])
    comparable = rw.get("comparable", [])
    closest = rw.get("closest_with_delta", {})
    fig_html = _anchor_figs_html(a, "related")

    if not foundational and not comparable and not closest and not fig_html:
        return ""

    def _work_item(w):
        title = esc(w.get("title", ""))
        authors = esc(w.get("authors", ""))
        year = esc(str(w.get("year", "")))
        why = esc_inline(w.get("why", ""))
        return f"<li><strong>{title}</strong> ({authors}, {year}): {why}</li>"

    found_items = "\n          ".join(_work_item(w) for w in foundational)
    comp_items = "\n          ".join(_work_item(w) for w in comparable)

    closest_title = esc(closest.get("title", ""))
    closest_year = esc(str(closest.get("year", "")))
    closest_delta = esc_inline(closest.get("key_delta", ""))

    return f"""
    <!-- ══ BLOCK 9 — RELATED WORK ════════════════════════════════════════════ -->
    <section id="related" class="paper-section">
      <h2>Related Work</h2>{fig_html}

      <div class="related-block">
        <p class="label">Foundational</p>
        <ul>
          {found_items}
        </ul>
      </div>

      <div class="related-block">
        <p class="label">Comparable</p>
        <ul>
          {comp_items}
        </ul>
      </div>

      <div class="related-block closest">
        <p class="label">Closest with key delta</p>
        <p><strong>{closest_title}</strong> ({closest_year})</p>
        <p>{closest_delta}</p>
      </div>
    </section>"""


def build_block10_limits(a: dict) -> str:
    """Block 10 — Limitations, Use Cases, Open Questions."""
    limitations = a.get("limitations", [])
    use_cases = a.get("use_cases", [])
    open_questions = a.get("open_questions", [])
    fig_html = _anchor_figs_html(a, "limits")

    if not limitations and not use_cases and not open_questions and not fig_html:
        return ""

    lim_items = ""
    for lim in limitations:
        limit = esc_inline(lim.get("limit", ""))
        softening = esc_inline(lim.get("softening", ""))
        lim_items += f"""
          <li>
            <p class="lim">{limit}</p>
            <p class="lim-soften"><em>{softening}</em></p>
          </li>"""

    uc_items = "".join(f"\n          <li>{esc_inline(u)}</li>" for u in use_cases)
    oq_items = "".join(f"\n          <li>{esc_inline(q)}</li>" for q in open_questions)

    return f"""
    <!-- ══ BLOCK 10 — LIMITATIONS / USE CASES / OPEN QUESTIONS ══════════════ -->
    <section id="limits" class="paper-section">
      <h2>Limitations, Use Cases, Open Questions</h2>{fig_html}

      <div class="lim-block">
        <p class="label">Limitations</p>
        <ul class="limit-list">{lim_items}
        </ul>
      </div>

      <div class="lim-block">
        <p class="label">Where this is useful</p>
        <ul>{uc_items}
        </ul>
      </div>

      <div class="lim-block">
        <p class="label">Open questions</p>
        <ul>{oq_items}
        </ul>
      </div>
    </section>"""


def build_block11_qa(a: dict) -> str:
    """Block 11 — Deep Q&A (reveal toggle)."""
    qa_items = a.get("qa", [])
    if not qa_items:
        return ""

    # Q&A type → display label + badge color (inherits via CSS class)
    TYPE_LABEL = {
        "intuition":   "Intuition",
        "principle":   "Principle",
        "detail":      "Detail",
        "limit":       "Limit",
        "boundary":    "Limit",
        "engineering": "Engineering",
        "extension":   "Extension",
    }

    items_html = ""
    for item in qa_items:
        q = esc_inline(item.get("q", ""))
        ans = esc_answer(item.get("a", ""))
        qtype = item.get("type")
        badge_html = ""
        if qtype in TYPE_LABEL:
            badge_html = f'<span class="qa-badge qa-badge-{qtype}">{TYPE_LABEL[qtype]}</span> '
        items_html += f"""
      <details class="qa-item">
        <summary>{badge_html}{q}</summary>
        <div class="qa-answer">{ans}</div>
      </details>"""

    return f"""
    <!-- ══ BLOCK 11 — DEEP Q&A ════════════════════════════════════════════════ -->
    <section id="qa" class="paper-section">
      <h2>Deep Q&amp;A</h2>
      <p class="section-intro">Open-ended questions to deepen understanding. Try to answer before clicking reveal. Badges show what kind of thinking each question is testing.</p>
{items_html}
    </section>"""


def build_block12_quiz(a: dict) -> str:
    """Block 12 — Self-Check Quiz."""
    quiz_items = a.get("quiz", [])
    if not quiz_items:
        return ""

    items_html = ""
    for item in quiz_items:
        q = esc_inline(item.get("q", ""))
        model_answer = esc_answer(item.get("model_answer", ""))
        items_html += f"""
      <details class="qa-item quiz-item">
        <summary>{q}</summary>
        <div class="qa-answer"><strong>Model answer.</strong> {model_answer}</div>
      </details>"""

    return f"""
    <!-- ══ BLOCK 12 — SELF-CHECK QUIZ ════════════════════════════════════════ -->
    <section id="quiz" class="paper-section">
      <h2>Self-Check Quiz</h2>
      <p class="section-intro">Imagine an interviewer who knows ML but hasn't read this paper. Answer aloud, then click to reveal a model answer.</p>
{items_html}
    </section>"""


def build_block13_sidebar(a: dict | None = None) -> str:
    """Block 13 — Sidebar (TOC + code refs). Pomodoro is now floating
    fixed-position so it stays visible while the sidebar's code refs scroll.

    Some TOC entries (e.g. 'Where it matters') only render when the
    corresponding optional block is populated.
    """
    # Optional blocks: only include the TOC link if the corresponding
    # analysis field is populated. Keeps clicks from dead-anchoring.
    wtm = (a or {}).get("where_this_matters") or {}
    context_li = ""
    if wtm.get("intro") or wtm.get("items"):
        context_li = '\n        <li><a href="#context" data-section-id="context">Where it matters</a></li>'

    timeline_li = ""
    if (a or {}).get("tech_timeline"):
        timeline_li = '\n        <li><a href="#timeline" data-section-id="timeline">Timeline</a></li>'

    comparison_li = ""
    comp = (a or {}).get("methods_comparison") or {}
    has_comparison_fig = any(
        f.get("anchor_section") == "comparison"
        for f in (a or {}).get("paper_figures", [])
    )
    if comp.get("headers") or comp.get("note") or has_comparison_fig:
        comparison_li = '\n        <li><a href="#comparison" data-section-id="comparison">Comparison</a></li>'

    exp = (a or {}).get("main_results") or {}
    has_experiment_fig = any(
        f.get("anchor_section") == "experiments"
        for f in (a or {}).get("paper_figures", [])
    )
    experiments_li = ""
    if (
        (a or {}).get("experiments_setup_summary")
        or exp.get("headline")
        or (exp.get("table") or {}).get("headers")
        or exp.get("ablations")
        or has_experiment_fig
    ):
        experiments_li = '\n        <li><a href="#experiments" data-section-id="experiments">Experiments</a></li>'

    rw = (a or {}).get("related_work") or {}
    has_related_fig = any(
        f.get("anchor_section") == "related"
        for f in (a or {}).get("paper_figures", [])
    )
    related_li = ""
    if rw.get("foundational") or rw.get("comparable") or rw.get("closest_with_delta") or has_related_fig:
        related_li = '\n        <li><a href="#related" data-section-id="related">Related Work</a></li>'

    has_limits_fig = any(
        f.get("anchor_section") == "limits"
        for f in (a or {}).get("paper_figures", [])
    )
    limits_li = ""
    if (
        (a or {}).get("limitations")
        or (a or {}).get("use_cases")
        or (a or {}).get("open_questions")
        or has_limits_fig
    ):
        limits_li = '\n        <li><a href="#limits" data-section-id="limits">Limits &amp; Open Qs</a></li>'

    qa_li = ""
    if (a or {}).get("qa"):
        qa_li = '\n        <li><a href="#qa" data-section-id="qa">Q&amp;A</a></li>'

    quiz_li = ""
    if (a or {}).get("quiz"):
        quiz_li = '\n        <li><a href="#quiz" data-section-id="quiz">Quiz</a></li>'

    return f"""
  <!-- ══ BLOCK 13 — SIDEBAR ═════════════════════════════════════════════════ -->
  <aside class="sidebar">
    <nav class="toc">
      <p class="label">On this page</p>
      <ol>
        <li><a href="#tldr" data-section-id="tldr">TL;DR</a></li>
        <li><a href="#overview" data-section-id="overview">Paper Overview</a></li>{timeline_li}{context_li}
        <li><a href="#method" data-section-id="method">Core Method</a></li>
        {experiments_li}
        {comparison_li}{related_li}{limits_li}{qa_li}{quiz_li}
      </ol>
    </nav>

    <div class="coderefs-wrap">
      <p class="label">Code refs <span class="hint">(click for full view)</span></p>
      <div id="coderefs"></div>
    </div>
  </aside>"""


def build_floating_widgets() -> str:
    """Floating, fixed-position widgets that live outside any scrolling
    container: the Pomodoro timer and the code-modal overlay.
    """
    return """
  <!-- ══ FLOATING POMODORO (fixed bottom-right of viewport) ══════════════════ -->
  <div class="pomodoro pomodoro-floating" id="pomodoro" role="region" aria-label="Focus timer">
    <button class="pomo-collapse" id="pomo-collapse" aria-label="Minimize">&#x2013;</button>
    <p class="label">Focus</p>
    <div class="pomo-display">
      <span id="pomo-mode" class="pomo-mode">Focus</span>
      <span id="pomo-time" class="pomo-time">25:00</span>
    </div>
    <div class="pomo-controls">
      <button id="pomo-toggle" class="pomo-btn" aria-label="Start/pause timer">&#9654;</button>
      <button id="pomo-reset" class="pomo-btn" aria-label="Reset timer">&#8634;</button>
    </div>
    <p id="pomo-stats" class="pomo-stats">0 pomodoros today</p>
  </div>

  <!-- ══ CODE MODAL (full-width snippet viewer) ════════════════════════════ -->
  <div class="code-modal" id="code-modal" role="dialog" aria-modal="true" aria-hidden="true">
    <div class="code-modal-backdrop" data-close></div>
    <div class="code-modal-panel">
      <header class="code-modal-header">
        <div>
          <p class="code-modal-meta" id="code-modal-meta"></p>
          <h3 class="code-modal-title" id="code-modal-title"></h3>
        </div>
        <button class="code-modal-close" data-close aria-label="Close">&times;</button>
      </header>
      <pre class="code-modal-body" id="code-modal-body"></pre>
      <footer class="code-modal-footer">
        <p class="code-modal-note" id="code-modal-note"></p>
        <a class="code-modal-link" id="code-modal-link" href="#" target="_blank" rel="noopener" hidden>View on GitHub ↗</a>
      </footer>
    </div>
  </div>"""


def build_tail(coderefs_sections: dict) -> str:
    """Script tags at body end."""
    coderefs_json = json.dumps(coderefs_sections, ensure_ascii=False, indent=2)
    return f"""
<!-- ── Inject code refs data ────────────────────────────────────────────────── -->
<script>
window.CODEREFS = {coderefs_json};
</script>

<script src="main.js" defer></script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Figure copying
# ---------------------------------------------------------------------------

def copy_figures(a: dict, figures_src: Path, out_dir: Path) -> list:
    """
    Copy figures referenced in analysis.json's paper_figures field to out/figures/.
    Returns list of (src_filename, destination_path) tuples for reporting.
    """
    paper_figures = a.get("paper_figures", [])
    if not paper_figures:
        return []

    out_figures = out_dir / "figures"
    out_figures.mkdir(exist_ok=True)

    copied = []
    missing = []
    for fig in paper_figures:
        src_name = fig.get("src", "")
        if not src_name:
            continue
        src_path = figures_src / src_name
        if src_path.exists():
            shutil.copy2(src_path, out_figures / src_name)
            copied.append(src_name)
        else:
            missing.append(src_name)

    if missing:
        print(f"  [warn] {len(missing)} figure(s) not found in --figures dir: {missing}")

    return copied


# ---------------------------------------------------------------------------
# Jargon pass over the full body HTML
# ---------------------------------------------------------------------------

def apply_jargon(body_html: str, jargon: dict) -> str:
    """Apply jargon wrapping to the assembled body HTML."""
    if not jargon:
        return body_html
    return _wrap_jargon(body_html, jargon)


def _wrap_code_anchors(body_html: str, coderefs_sections: dict) -> str:
    """For each ref with anchor_phrase, wrap first occurrence in the matching
    <section id="..."> body with <span class="code-anchor">."""
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(body_html, "html.parser")
    for section_id, refs in coderefs_sections.items():
        if not refs:
            continue
        sec = soup.find("section", id=section_id)
        if sec is None:
            # A ref points at a section that isn't in the rendered body. Its
            # anchor_phrase can never wrap. Warn loudly: this is otherwise a
            # silent dead anchor.
            if any(r.get("anchor_phrase") for r in refs):
                print(f"  [warn] code-ref section '{section_id}' not found in body; "
                      f"{sum(1 for r in refs if r.get('anchor_phrase'))} anchor(s) skipped")
            continue
        for idx, ref in enumerate(refs):
            phrase = ref.get("anchor_phrase")
            if not phrase:
                continue
            title = ref.get("title", "")
            matched = False
            # Search NavigableString nodes inside this section, skipping
            # elements that are inside .explain / pre / code / .code-anchor.
            def _skip(node):
                p = node.parent
                while p is not None and p != sec:
                    cls = p.get("class", []) if hasattr(p, "get") else []
                    if "explain" in cls or "code-anchor" in cls or "jargon" in cls:
                        return True
                    # Skip headings (h2/h3/h4) and structural / non-prose elements
                    if p.name in ("pre", "code", "script", "style",
                                  "h1", "h2", "h3", "h4", "h5", "h6",
                                  "figcaption", "summary"):
                        return True
                    p = p.parent
                return False

            text_nodes = sec.find_all(string=True)
            for text_node in text_nodes:
                if not isinstance(text_node, NavigableString):
                    continue
                if _skip(text_node):
                    continue
                text = str(text_node)
                pos = _find_outside_math(text, phrase)
                if pos < 0:
                    continue
                before, after = text[:pos], text[pos + len(phrase):]
                span_html = (
                    f'<span class="code-anchor" '
                    f'data-coderef-section="{section_id}" '
                    f'data-coderef-idx="{idx}" '
                    f'title="{html_lib.escape(title)}">'
                    f'{html_lib.escape(phrase)}</span>'
                )
                new = BeautifulSoup(
                    html_lib.escape(before) + span_html + html_lib.escape(after),
                    "html.parser",
                )
                text_node.replace_with(new)
                matched = True
                break  # first occurrence per ref
            if not matched:
                # The phrase never appeared as plain prose in this section
                # (typo, or it only occurs inside <code>/<pre>/heading, which
                # the matcher skips). The ref renders in the sidebar but has no
                # clickable in-body anchor. Surface it instead of dropping it.
                print(f"  [warn] anchor_phrase not found in <section id='{section_id}'>: "
                      f"{phrase!r} (ref: {title[:50]!r}) — check it appears as plain "
                      f"text, not inside <code>/<pre>/heading")
    return str(soup)


def apply_code_anchors(body_html: str, coderefs_sections: dict) -> str:
    if not coderefs_sections:
        return body_html
    return _wrap_code_anchors(body_html, coderefs_sections)


_MERMAID_BLOCK_RE = re.compile(
    r'(<pre class="mermaid">)(.*?)(</pre>)', re.DOTALL
)


def fix_mermaid_blocks(body_html: str) -> str:
    """BeautifulSoup re-serializes <pre> content and escapes &gt; / &lt; / &amp;,
    which breaks Mermaid's `-->` and `<br/>` syntax. Run after all BS4 passes
    to restore Mermaid source verbatim.

    Replaces the escaped characters only inside `<pre class="mermaid">` blocks
    — leaves all other pre/code blocks alone.
    """
    def _unescape_block(match):
        opening, content, closing = match.group(1), match.group(2), match.group(3)
        content = (
            content.replace("&gt;", ">")
                   .replace("&lt;", "<")
                   .replace("&amp;", "&")
        )
        return opening + content + closing

    return _MERMAID_BLOCK_RE.sub(_unescape_block, body_html)


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

def validate_schema(a: dict, coderefs_raw) -> list[str]:
    """Validate the SHAPE of analysis.json / coderefs.json before rendering.

    Returns a list of human-readable error strings (empty == OK). This catches
    the type/field mistakes that otherwise crash the block builders mid-render
    (e.g. related_work.closest_with_delta as a string, limitations as strings,
    coderefs as a bare list) and the silent-empty mistakes the post-render
    checks miss (e.g. a quiz item whose answer is under "a" instead of
    "model_answer", which renders a blank "Model answer."). All problems are
    collected and reported at once instead of failing on the first.
    """
    errs = []

    def want(cond, msg):
        if not cond:
            errs.append(msg)

    want(isinstance(a.get("title"), str) and a.get("title"),
         'title: must be a non-empty string')

    want(isinstance(a.get("tldr"), (dict, str)),
         'tldr: must be an object {summary} or a string')

    ov = a.get("paper_overview")
    if ov is not None:
        want(isinstance(ov, dict), 'paper_overview: must be an object')
        if isinstance(ov, dict):
            want(isinstance(ov.get("contributions", []), list),
                 'paper_overview.contributions: must be a list')

    tl = a.get("tech_timeline")
    if tl is not None:
        want(isinstance(tl, list) and tl, 'tech_timeline: must be a non-empty list')
        if isinstance(tl, list):
            want(any(isinstance(n, dict) and n.get("current") for n in tl),
                 'tech_timeline: exactly one node needs "current": true')

    ms = a.get("method_subsections")
    if ms is not None:
        want(isinstance(ms, list), 'method_subsections: must be a list')
        for i, s in enumerate(ms or []):
            want(isinstance(s, dict) and (s.get("body_html_file") or s.get("body_html")),
                 f'method_subsections[{i}]: needs "body_html_file" or "body_html"')

    rw = a.get("related_work")
    if isinstance(rw, dict) and "closest_with_delta" in rw:
        want(isinstance(rw["closest_with_delta"], dict),
             'related_work.closest_with_delta: must be an OBJECT '
             '{title, year, key_delta}, not a string')

    lims = a.get("limitations")
    if lims is not None:
        want(isinstance(lims, list), 'limitations: must be a list')
        for i, l in enumerate(lims or []):
            want(isinstance(l, dict) and isinstance(l.get("limit"), str) and l.get("limit"),
                 f'limitations[{i}]: must be an OBJECT with a non-empty "limit" '
                 '(and ideally "softening"), not a string')

    for i, q in enumerate(a.get("qa", []) or []):
        want(isinstance(q, dict) and q.get("q") and q.get("a"),
             f'qa[{i}]: needs non-empty "q" and "a"')

    for i, q in enumerate(a.get("quiz", []) or []):
        if not isinstance(q, dict):
            errs.append(f'quiz[{i}]: must be an object')
            continue
        want(q.get("q"), f'quiz[{i}]: needs a non-empty "q"')
        want(q.get("model_answer"),
             f'quiz[{i}]: needs a non-empty "model_answer" '
             '(the field is "model_answer", not "a" as in qa)')

    for i, fig in enumerate(a.get("paper_figures", []) or []):
        want(isinstance(fig, dict) and fig.get("src") and fig.get("caption"),
             f'paper_figures[{i}]: needs "src" and "caption"')

    if isinstance(coderefs_raw, list):
        errs.append('coderefs.json: top level must be an object {"refs": [...]}, '
                    'not a bare list')
    elif isinstance(coderefs_raw, dict) and isinstance(coderefs_raw.get("refs"), list):
        for i, r in enumerate(coderefs_raw["refs"]):
            want(isinstance(r, dict) and r.get("section") and r.get("url"),
                 f'coderefs.refs[{i}]: needs "section" and "url"')

    return errs


# Correctly-shaped empty templates emitted by --scaffold. They pass
# validate_schema as-is, so authors edit known-good structure instead of
# rediscovering field names by trial and error.
SCAFFOLD_ANALYSIS = {
    "title": "TODO paper title",
    "authors": "TODO authors",
    "venue": "TODO venue",
    "year": 2025,
    "subtitle": "TODO one concrete sentence",
    "difficulty": 3,
    "difficulty_label": "TODO name what is hard",
    "estimated_reading_time": "15 min",
    "tags": ["todo"],
    "paper_url": "TODO",
    "author_repo": None,
    "prerequisites": [
        {"term": "TODO", "brief": "TODO", "beginner_link": "TODO",
         "beginner_title": "TODO", "primary_link": "TODO", "primary_title": "TODO"}
    ],
    "tldr": {"summary": "TODO 2-3 sentences: bottleneck, mechanism, strongest payoff."},
    "paper_overview": {
        "problem": "TODO", "background": "TODO", "solution": "TODO",
        "contributions": ["TODO"]
    },
    "tech_timeline": [
        {"year": 2024, "label": "TODO predecessor", "delta": "TODO one change"},
        {"year": 2025, "label": "TODO this paper", "current": True, "delta": "TODO"}
    ],
    "method_subsections": [
        {"title": "TODO subsection", "body_html_file": "sections/01-todo.html"}
    ],
    "experiments_setup_summary": "TODO",
    "main_results": {
        "headline": "TODO",
        "table": {"headers": ["TODO"], "rows": [["TODO"]], "highlight_row": 0},
        "ablations": ["TODO"]
    },
    "related_work": {
        "closest_with_delta": {"title": "TODO", "year": 2024, "key_delta": "TODO"}
    },
    "limitations": [{"limit": "TODO", "softening": "TODO"}],
    "use_cases": ["TODO"],
    "open_questions": ["TODO"],
    "paper_figures": [],
    "qa": [{"type": "principle", "q": "TODO?", "a": "TODO"}],
    "quiz": [{"q": "TODO?", "model_answer": "TODO"}]
}
SCAFFOLD_CODEREFS = {
    "refs": [
        {"section": "method", "source": "author_repo", "title": "TODO",
         "repo": "owner/repo", "path": "path/to/file",
         "url": "https://github.com/owner/repo/blob/main/file#L1-L20",
         "anchor_phrase": "the mechanism this code implements",
         "snippet": "# TODO short preview", "note": "TODO why this ref matters"}
    ]
}


def write_scaffold(out_dir: Path):
    """Emit correctly-shaped empty analysis.json + coderefs.json (and a stub
    method section) so authors start from valid structure."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sections").mkdir(exist_ok=True)
    (out_dir / "analysis.json").write_text(
        json.dumps(SCAFFOLD_ANALYSIS, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "coderefs.json").write_text(
        json.dumps(SCAFFOLD_CODEREFS, indent=2, ensure_ascii=False), encoding="utf-8")
    stub = out_dir / "sections" / "01-todo.html"
    if not stub.exists():
        # Include the example coderef's anchor_phrase so the scaffold passes
        # --check out of the box.
        stub.write_text(
            "<p>TODO method subsection body. Describe the mechanism this code "
            "implements so the code reference has a prose anchor.</p>\n",
            encoding="utf-8")
    print(f"Scaffold written to {out_dir}/:")
    print("  analysis.json   (correctly-shaped, fill the TODO fields)")
    print("  coderefs.json   ({\"refs\": [...]} shape)")
    print("  sections/01-todo.html")


def assemble(
    analysis_path: Path,
    coderefs_path: Path,
    figures_dir: Path,
    assets_dir: Path,
    out_dir: Path,
    check: bool = False,
):
    # 1. Load data
    print(f"Loading analysis: {analysis_path}")
    with open(analysis_path, encoding="utf-8") as f:
        a = json.load(f)

    # Resolve body_html_file -> body_html. Authoring long, code-heavy sections as
    # standalone .html files avoids escaping LaTeX backslashes, quotes, and Python
    # docstrings inside JSON. Path is relative to analysis.json's directory.
    base_dir = analysis_path.parent
    missing_body_html_files = []

    def _inline_html(obj):
        if isinstance(obj, dict) and obj.get("body_html_file") and not obj.get("body_html"):
            p = base_dir / obj["body_html_file"]
            try:
                obj["body_html"] = p.read_text(encoding="utf-8")
            except OSError:
                print(f"  [warn] body_html_file not found: {p}", file=sys.stderr)
                obj["body_html"] = ""
                missing_body_html_files.append(str(p))

    for _sub in a.get("method_subsections", []):
        _inline_html(_sub)
    _inline_html((a.get("paper_overview") or {}).get("background"))
    if missing_body_html_files:
        a["_missing_body_html_files"] = missing_body_html_files

    print(f"Loading coderefs: {coderefs_path}")
    with open(coderefs_path, encoding="utf-8") as f:
        coderefs = json.load(f)

    # Fail fast on shape errors with ALL problems at once, before the block
    # builders touch the data and crash on the first bad field.
    schema_errors = validate_schema(a, coderefs)
    if schema_errors:
        print("\n" + "=" * 60)
        print("  SCHEMA VALIDATION FAILED")
        print("=" * 60)
        for e in schema_errors:
            print(f"  [FAIL] {e}")
        print("=" * 60)
        print(f"  {len(schema_errors)} problem(s); fix analysis.json / coderefs.json "
              "and re-run.\n")
        sys.exit(1)

    # Three accepted shapes for coderefs.json:
    #   1. {"sections": {"method": [refs], "online": [refs], ...}}
    #   2. {"method": [refs], "online": [refs], ...}              (top-level)
    #   3. {"refs": [<ref-with-section-field>, ...]}             (flat list)
    # If we get (3), regroup by each ref's "section" field so the wrap +
    # sidebar code can index by section_id like the other two shapes.
    if "refs" in coderefs and isinstance(coderefs["refs"], list):
        coderefs_sections = {}
        for ref in coderefs["refs"]:
            sid = ref.get("section") or "method"
            coderefs_sections.setdefault(sid, []).append(ref)
    else:
        coderefs_sections = coderefs.get("sections", coderefs)

    # 2. Set up output directory
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(exist_ok=True)

    # 3. Copy assets
    styles_src = assets_dir / "styles.css"
    mainjs_src = assets_dir / "main.js"
    assets_copied = []
    if styles_src.exists():
        shutil.copy2(styles_src, out_dir / "styles.css")
        assets_copied.append("styles.css")
    else:
        print(f"  [warn] assets/styles.css not found at {styles_src}")

    if mainjs_src.exists():
        shutil.copy2(mainjs_src, out_dir / "main.js")
        assets_copied.append("main.js")
    else:
        print(f"  [warn] assets/main.js not found at {mainjs_src}")

    # 4. Copy referenced figures
    if figures_dir and figures_dir.exists():
        copied = copy_figures(a, figures_dir, out_dir)
        if copied:
            print(f"  Copied {len(copied)} figure(s): {copied}")
    else:
        if figures_dir:
            print(f"  [warn] --figures dir not found: {figures_dir}")

    # 4b. Copy the original paper alongside the note, so the output is self-contained.
    paper_src = analysis_path.parent / "paper.pdf"
    if paper_src.exists():
        shutil.copy2(paper_src, out_dir / "paper.pdf")
        print("  Copied original paper: paper.pdf")

    # 5. Build HTML blocks
    jargon = a.get("jargon", {})

    head = build_head(a)
    block1 = build_block1_header(a)
    block2 = build_block2_prereqs(a)

    body_open = """
<div class="page-wrapper">
"""

    reader_open = """
  <!-- ══ READER GRID ════════════════════════════════════════════════════════ -->
  <div class="reader">
  <article>
"""

    block3 = build_block3_tldr(a)
    block3b = build_block3b_overview(a)
    block5 = build_block5_timeline(a)
    block5b = build_block5b_where_this_matters(a)
    block6 = build_block6_method(a)
    block7 = build_block7_experiments(a)
    block8 = build_block8_comparison(a)
    block9 = build_block9_related(a)
    block10 = build_block10_limits(a)
    block11 = build_block11_qa(a)
    block12 = build_block12_quiz(a)

    reader_close = """
  </article>
"""
    block13 = build_block13_sidebar(a)
    floating = build_floating_widgets()
    grid_close = """
  </div><!-- end .reader -->
</div><!-- end .page-wrapper -->
""" + floating

    tail = build_tail(coderefs_sections)

    # Assemble body content (for jargon pass)
    body_content = (
        body_open
        + block1
        + block2
        + reader_open
        + block3
        + block3b
        + block5
        + block5b
        + block6
        + block7
        + block8
        + block9
        + block10
        + block11
        + block12
        + reader_close
        + block13
        + grid_close
    )

    # 6. Apply jargon wrapping to body content
    if jargon:
        print(f"  Applying jargon wrapping for {len(jargon)} terms...")
        body_content = apply_jargon(body_content, jargon)

    # 6b. Wrap code anchors (links body phrases to sidebar code refs)
    n_anchored = sum(
        1 for refs in coderefs_sections.values()
        for r in refs if r.get("anchor_phrase")
    )
    if n_anchored:
        print(f"  Wrapping {n_anchored} code anchor(s)...")
        body_content = apply_code_anchors(body_content, coderefs_sections)

    # 6c. Restore Mermaid `-->` / `<br/>` syntax escaped by BS4 (jargon/anchor
    #     passes re-serialize HTML and break the Mermaid parser otherwise).
    body_content = fix_mermaid_blocks(body_content)

    # 7. Assemble final HTML
    html = head + "\n" + body_content + tail

    # 8. Write index.html
    index_path = out_dir / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    line_count = html.count("\n") + 1

    # 9. Print summary
    print()
    print("=" * 60)
    print("  Yomitoki reader assembled successfully")
    print("=" * 60)
    print(f"  Output dir   : {out_dir}")
    print(f"  index.html   : {line_count} lines")
    print(f"  Assets copied: {assets_copied}")
    print(f"  Paper        : {a.get('title', '(unknown)')}")
    rendered_sections = [
        label for section_id, label in [
            ("tldr", "TL;DR"),
            ("overview", "Overview"),
            ("timeline", "Timeline"),
            ("context", "Where it matters"),
            ("method", "Method"),
            ("experiments", "Experiments"),
            ("comparison", "Comparison"),
            ("related", "Related"),
            ("limits", "Limits"),
            ("qa", "Q&A"),
            ("quiz", "Quiz"),
        ]
        if f'id="{section_id}"' in body_content
    ]
    print(f"  Sections     : {', '.join(rendered_sections + ['Sidebar'])}")
    print("=" * 60)
    print()
    print(f"  Open in browser: file://{index_path.resolve()}")

    if check:
        return run_checks(a, coderefs_sections, figures_dir, html)
    return 0


# ---------------------------------------------------------------------------
# Quality checks (--check)
# ---------------------------------------------------------------------------

# Valid code-ref section IDs (mirror of references/code-ref-waterfall.md).
_VALID_SECTIONS = {
    "tldr", "overview", "timeline", "context", "method", "experiments",
    "comparison", "related", "limits", "qa", "quiz",
}

_VALID_FIGURE_SECTIONS = {
    "header", "overview", "motivation", "method", "experiments",
    "comparison", "related", "limits", "inline",
}


def _walk_strings(obj, path=""):
    """Yield (dotted-path, string) for every string value in a nested dict/list."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


_IDENTITY_STRING_PATHS = {
    "title", "subtitle", "authors", "venue", "paper_url", "author_repo",
    "arxiv_id", "arxiv_url",
}


def _anchor_phrase_issue(phrase: str) -> str | None:
    """Return a human-readable issue when an anchor phrase is likely to render
    as a weird code pointer instead of a useful prose hook."""
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", phrase or "")
    if len(words) < 4:
        return "too short; use a 4-10 word prose phrase"
    if len(words) > 14:
        return "too long; fragile exact match"
    if re.search(r"`|<code|</code>|::|->|=>|[A-Za-z_]\w*\(|\b\w+\.(?:py|cpp|cu|js|ts|forward|backward)\b|[{};]", phrase):
        return "looks code-like; anchor on surrounding prose instead"
    if re.search(r"^\W*[A-Za-z_]\w*\W*$", phrase or ""):
        return "single identifier; anchor on surrounding prose instead"
    return None


def run_checks(a: dict, coderefs_sections: dict, figures_dir, html: str) -> int:
    """Consolidated quality report run after assembly.

    Hard failures (exit non-zero): dead or malformed code anchors,
    duplicate/missing/unreferenced figures, unbalanced KaTeX delimiters,
    invalid code-ref sections, authored em-dashes (the writing rules ban them;
    warning-only previously let them slip through).
    Warnings (exit zero): partial jargon coverage and storage hygiene.
    Returns the number of hard failures.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        anchor_texts = [s.get_text() for s in soup.select("span.code-anchor")]
        jargon_actual = len(soup.select("span.jargon"))
        dead_toc_links = [
            a.get("href")
            for a in soup.select(".toc a[href^='#']")
            if not soup.find(id=(a.get("href") or "#")[1:])
        ]
    except ImportError:
        anchor_texts = None
        jargon_actual = html.count('class="jargon"')
        dead_toc_links = []

    lines = []      # (tag, message); tag "" = continuation line
    n_fail = n_warn = 0

    # 1. Code anchors — every anchor_phrase must end up inside a code-anchor span
    expected = [(sid, r["anchor_phrase"])
                for sid, refs in coderefs_sections.items()
                for r in refs if r.get("anchor_phrase")]
    if anchor_texts is None:
        actual = html.count('class="code-anchor"')
        tag = "FAIL" if actual < len(expected) else "PASS"
        n_fail += tag == "FAIL"
        lines.append((tag, f"code anchors        {actual}/{len(expected)} wrapped (install bs4 to name dead ones)"))
    else:
        dead = [ph for _, ph in expected if not any(ph in t for t in anchor_texts)]
        if dead:
            n_fail += 1
            lines.append(("FAIL", f"code anchors        {len(expected) - len(dead)}/{len(expected)} wrapped; dead anchor_phrase(s):"))
            lines += [("", f"                      - {ph!r}") for ph in dead]
        else:
            lines.append(("PASS", f"code anchors        {len(expected)}/{len(expected)} wrapped"))

    # 1b. Code anchor phrase quality — bad phrases render as strange inline
    #     pointers, even when the exact text match succeeds.
    bad_phrases = [
        (sid, phrase, issue)
        for sid, phrase in expected
        if (issue := _anchor_phrase_issue(phrase))
    ]
    if bad_phrases:
        n_fail += 1
        lines.append(("FAIL", f"anchor phrases      {len(bad_phrases)} need rewrite:"))
        lines += [
            ("", f"                      - [{sid}] {phrase!r}: {issue}")
            for sid, phrase, issue in bad_phrases[:8]
        ]
        if len(bad_phrases) > 8:
            lines.append(("", f"                      … and {len(bad_phrases) - 8} more"))
    else:
        lines.append(("PASS", "anchor phrases      prose-shaped"))

    # 1c. Orphan method refs — method refs without anchor_phrase render as
    #     side-panel cards with no in-prose trigger. WARN, not FAIL: a
    #     "here's the whole project" overview ref attached to method is
    #     occasionally legitimate.
    method_refs = coderefs_sections.get("method", [])
    method_orphans = [r for r in method_refs if not r.get("anchor_phrase")]
    if method_orphans:
        n_warn += 1
        lines.append(("WARN", f"method orphans      {len(method_orphans)} method ref(s) without anchor_phrase (orphan side-panel cards):"))
        lines += [
            ("", f"                      - {(r.get('title') or r.get('repo') or r.get('url') or '?')!r}")
            for r in method_orphans[:5]
        ]
        if len(method_orphans) > 5:
            lines.append(("", f"                      … and {len(method_orphans) - 5} more"))
    else:
        lines.append(("PASS", "method orphans      all method refs have anchor_phrase"))

    # 2. Figures — declared files must exist on disk and be referenced in the html
    figs = a.get("paper_figures", [])
    fig_ids = [f.get("id") for f in figs if f.get("id")]
    fig_srcs = [f.get("src") for f in figs if f.get("src")]
    duplicate_ids = sorted({x for x in fig_ids if fig_ids.count(x) > 1})
    duplicate_srcs = sorted({
        src for src in fig_srcs
        if sum(1 for f in figs if f.get("src") == src and f.get("anchor_section") != "inline") > 1
    })
    bad_fig_sections = sorted({
        f.get("anchor_section")
        for f in figs
        if f.get("anchor_section") and f.get("anchor_section") not in _VALID_FIGURE_SECTIONS
    })
    missing_source_dir = bool(figs and not figures_dir)
    missing = [f["src"] for f in figs if f.get("src") and figures_dir and not (figures_dir / f["src"]).exists()]
    unref = [f["src"] for f in figs if f.get("src") and f'figures/{f["src"]}' not in html]
    repeated_render = sorted({
        src for src in fig_srcs
        if src and html.count(f'figures/{src}') > 1
    })
    if duplicate_ids or duplicate_srcs or bad_fig_sections or missing_source_dir or missing or unref or repeated_render:
        n_fail += 1
        msg = f"figures             {len(figs)} declared"
        if duplicate_ids:
            msg += f"; DUPLICATE ids: {duplicate_ids}"
        if duplicate_srcs:
            msg += f"; DUPLICATE src declarations: {duplicate_srcs}"
        if bad_fig_sections:
            msg += f"; INVALID anchor_section: {bad_fig_sections}"
        if missing_source_dir:
            msg += "; --figures dir required when paper_figures are declared"
        if missing:
            msg += f"; MISSING on disk: {missing}"
        if unref:
            msg += f"; NOT referenced: {unref}"
        if repeated_render:
            msg += f"; RENDERED multiple times: {repeated_render}"
        lines.append(("FAIL", msg))
    else:
        lines.append(("PASS", f"figures             {len(figs)}/{len(figs)} found and referenced"))

    # 2b. Mermaid coverage. This is informational only: the skill now asks for
    #     diagrams when they reduce working memory, not to hit a quota.
    mermaid_count = len(re.findall(r'<pre\s+class=["\']mermaid["\']', html))
    lines.append(("PASS", f"Mermaid coverage    {mermaid_count} diagram(s)"))

    # 2c. Long method HTML should live in section files, not inside JSON.
    inline_heavy = [
        (i, sub.get("title") or sub.get("heading") or f"subsection {i + 1}", len(sub.get("body_html", "")))
        for i, sub in enumerate(a.get("method_subsections", []))
        if not sub.get("body_html_file") and len(sub.get("body_html", "")) > 500
    ]
    if inline_heavy:
        n_warn += 1
        lines.append(("WARN", f"body_html storage   {len(inline_heavy)} long inline method section(s); prefer body_html_file:"))
        lines += [
            ("", f"                      - #{i + 1} {title!r}: {n} chars")
            for i, title, n in inline_heavy[:6]
        ]
    else:
        lines.append(("PASS", "body_html storage   method sections use files or stay small"))

    missing_body_files = a.get("_missing_body_html_files", [])
    if missing_body_files:
        n_fail += 1
        lines.append(("FAIL", f"body_html files     missing {len(missing_body_files)} file(s):"))
        lines += [("", f"                      - {p}") for p in missing_body_files[:8]]
    else:
        lines.append(("PASS", "body_html files     all referenced files found"))

    # 3. KaTeX delimiters — opens must match closes; $$ count must be even
    ob, cb = html.count(r"\["), html.count(r"\]")
    oi, ci = html.count(r"\("), html.count(r"\)")
    dd = html.count("$$")
    if ob != cb or oi != ci or dd % 2:
        n_fail += 1
        lines.append(("FAIL", rf"KaTeX delimiters    \[ {ob} vs \] {cb} · \( {oi} vs \) {ci} · $$ {dd} (must balance)"))
    else:
        lines.append(("PASS", rf"KaTeX delimiters    \[\] {ob} pairs · \(\) {oi} pairs · $$ {dd // 2} pairs"))

    # 4. Code-ref sections — invalid IDs are silently dropped by the loader
    bad = sorted(s for s in coderefs_sections if s not in _VALID_SECTIONS)
    if bad:
        n_fail += 1
        lines.append(("FAIL", f"coderef sections    invalid (refs dropped): {bad}"))
    else:
        lines.append(("PASS", "coderef sections    all valid"))

    if dead_toc_links:
        n_fail += 1
        lines.append(("FAIL", f"TOC links           dead anchors: {dead_toc_links}"))
    else:
        lines.append(("PASS", "TOC links           all rendered sections exist"))

    timeline_nodes = a.get("tech_timeline") or []
    current_nodes = [n for n in timeline_nodes if n.get("current") is True]
    if not timeline_nodes:
        n_fail += 1
        lines.append(("FAIL", "tech timeline       missing required tech_timeline"))
    elif not current_nodes:
        n_fail += 1
        lines.append(("FAIL", "tech timeline       no node marked current: true"))
    else:
        lines.append(("PASS", f"tech timeline       {len(timeline_nodes)} node(s), current marked"))

    # 5. Em-dashes in authored prose (hard failure — banned by the writing rules;
    #    warning-only previously let them slip through to the rendered reader).
    em_hits = [
        (path, s[max(0, m.start() - 25):m.end() + 25].replace("\n", " "))
        for path, s in _walk_strings(a)
        if path not in _IDENTITY_STRING_PATHS and not path.startswith("_")
        for m in re.finditer("—", s)
    ]
    if em_hits:
        n_fail += 1
        lines.append(("FAIL", f"em-dashes (authored) {len(em_hits)} in analysis.json:"))
        lines += [("", f"                      - {path}: …{ctx}…") for path, ctx in em_hits[:8]]
        if len(em_hits) > 8:
            lines.append(("", f"                      … and {len(em_hits) - 8} more"))
    else:
        lines.append(("PASS", "em-dashes (authored) 0 in analysis.json"))

    # 6. Jargon coverage. Name the unwrapped terms and classify each as
    #    "only in code/aside (safe)" vs. "not present anywhere (likely typo)".
    #    Only the latter is worth fixing; the former is normal.
    jargon = a.get("jargon", {})
    jarg_total = len(jargon)
    if jarg_total and jargon_actual < jarg_total:
        try:
            from bs4 import BeautifulSoup
            soup_full = BeautifulSoup(html, "html.parser")
            wrapped_terms = {s.get_text() for s in soup_full.select("span.jargon")}
            # Whole-document text vs. text minus <pre>/<code>/<aside class="explain">.
            full_text = soup_full.get_text()
            stripped = BeautifulSoup(html, "html.parser")
            for el in stripped.find_all(["pre", "code"]):
                el.decompose()
            for el in stripped.find_all("aside", class_="explain"):
                el.decompose()
            prose_text = stripped.get_text()
        except ImportError:
            wrapped_terms = set()
            full_text = html
            prose_text = html

        safe = []         # term present only in code/aside — no action needed
        missing = []      # term absent entirely — likely a typo
        for term in jargon:
            if term in wrapped_terms:
                continue
            if term in prose_text:
                # Term appears in prose but somehow wasn't wrapped (shouldn't happen
                # given the wrapper, but surface it so the author can investigate).
                missing.append((term, "in prose but not wrapped (wrapper bug?)"))
            elif term in full_text:
                safe.append(term)
            else:
                missing.append((term, "absent from rendered HTML (typo? renamed?)"))

        if missing:
            n_warn += 1
            lines.append(("WARN", f"jargon              {jargon_actual}/{jarg_total} wrapped; {len(missing)} need attention:"))
            for term, why in missing:
                lines.append(("", f"                      - {term!r}: {why}"))
            if safe:
                lines.append(("", f"                      ({len(safe)} other term(s) only in code/aside — safe to ignore: {safe})"))
        else:
            # Everything unwrapped is just code/aside-only, which is fine.
            lines.append(("PASS", f"jargon              {jargon_actual}/{jarg_total} wrapped ({len(safe)} only in code/aside, safe)"))
    else:
        lines.append(("PASS", f"jargon              {jargon_actual}/{jarg_total} terms wrapped"))

    print()
    print("=" * 60)
    print("  CHECK REPORT")
    print("=" * 60)
    for tag, msg in lines:
        print(f"  [{tag}] {msg}" if tag else msg)
    print("=" * 60)
    result = "FAIL" if n_fail else ("PASS (with warnings)" if n_warn else "PASS")
    print(f"  RESULT: {result}  ({n_fail} failure(s), {n_warn} warning(s))")
    print("=" * 60)
    return n_fail


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Assemble a yomitoki HTML reader from analysis + coderefs + figures + assets."
    )
    parser.add_argument("--analysis", help="Path to analysis.json")
    parser.add_argument("--coderefs", help="Path to coderefs.json")
    parser.add_argument(
        "--figures", default=None, help="Directory containing figure PNGs"
    )
    parser.add_argument(
        "--assets",
        help="Directory containing styles.css and main.js",
    )
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument(
        "--scaffold",
        action="store_true",
        help="Write correctly-shaped empty analysis.json + coderefs.json (and a "
             "stub method section) to --out and exit, so authoring starts from "
             "valid structure. Ignores --analysis/--coderefs/--assets.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="After assembling, print a quality report (dead anchors, missing "
             "figures, duplicate figures, Mermaid count, unbalanced KaTeX, "
             "authored em-dashes, jargon coverage) "
             "and exit non-zero on any hard failure.",
    )
    args = parser.parse_args()

    if args.scaffold:
        write_scaffold(Path(args.out))
        return

    missing = [f"--{n}" for n in ("analysis", "coderefs", "assets")
               if not getattr(args, n)]
    if missing:
        parser.error("the following arguments are required: " + ", ".join(missing))

    analysis_path = Path(args.analysis)
    coderefs_path = Path(args.coderefs)
    figures_dir = Path(args.figures) if args.figures else None
    assets_dir = Path(args.assets)
    out_dir = Path(args.out)

    if not analysis_path.exists():
        print(f"ERROR: analysis file not found: {analysis_path}", file=sys.stderr)
        sys.exit(1)
    if not coderefs_path.exists():
        print(f"ERROR: coderefs file not found: {coderefs_path}", file=sys.stderr)
        sys.exit(1)

    n_fail = assemble(
        analysis_path=analysis_path,
        coderefs_path=coderefs_path,
        figures_dir=figures_dir,
        assets_dir=assets_dir,
        out_dir=out_dir,
        check=args.check,
    )
    if args.check and n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
