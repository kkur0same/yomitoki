# yomitoki

Turn a research paper into a faithful, technical, code-augmented HTML reading note.

`yomitoki` (読み解き, "reading and interpreting") is an [agent skill](https://docs.claude.com/en/docs/claude-code/skills) plus a small Python toolchain that converts a paper (arXiv link, arXiv ID, PDF path, or PDF URL) into a self-contained HTML study note. The note is written like a strong technical blog post: it leads with the contrast between the old approach and the paper's move, anchors figures to the prose they explain, and links claims to real source-code line ranges.

A finished note answers five questions:

1. Why did this paper need to exist?
2. What exactly is the move the paper makes?
3. Why does that move work?
4. Where does it win, by how much, and where does it stop winning?
5. How would I start implementing or verifying it?

## What it produces

A single `index.html` (plus `styles.css`, `main.js`, and curated `figures/`) containing: header metadata, prerequisites, TL;DR, paper overview, a verified tech-lineage timeline, a code-augmented core-method section, experiments, a methods comparison, limitations, and a Q&A + quiz. KaTeX renders math; Mermaid renders schematics when the paper warrants one.

## How it works

The pipeline is two scripts plus a model-authored intermediate JSON:

```
paper (arXiv / PDF)
   │   scripts/extract.py
   ▼
extracted.txt + figures/ + figures.json + skeleton analysis.json
   │   you (or an agent) author analysis.json + coderefs.json + sections/*.html
   ▼
   │   scripts/assemble.py --check
   ▼
index.html  (self-contained reading note)
```

`extract.py` pulls text and figures from the paper. A human or an agent then authors `analysis.json` (the note's content) and `coderefs.json` (code references), following the contracts in [`references/`](references/). `assemble.py` renders everything to HTML and validates it with `--check` (anchor phrases, figure references, KaTeX delimiters, timeline, and more).

## Use as a Claude Code skill

Clone into your skills directory so the agent can invoke it:

```bash
git clone git@github.com:kkur0same/yomitoki.git ~/.claude/skills/yomitoki
```

Then in Claude Code: `/yomitoki <arxiv-url | pdf-path | paper-title>`. The agent reads [`SKILL.md`](SKILL.md) and drives the workflow end to end. (Works with any harness that loads `SKILL.md`-style skills.)

## Use standalone

```bash
pip install -r requirements.txt          # pypdf, pymupdf; pandoc optional

# 1. Extract
python3 scripts/extract.py <arxiv-url|pdf-path|pdf-url> --out /tmp/yomitoki/my-paper/

# 2. Author /tmp/yomitoki/my-paper/analysis.json and coderefs.json
#    (see references/authoring-guide.md and references/code-ref-waterfall.md)

# 3. Assemble + validate
python3 scripts/assemble.py \
  --analysis  /tmp/yomitoki/my-paper/analysis.json \
  --coderefs  /tmp/yomitoki/my-paper/coderefs.json \
  --figures   /tmp/yomitoki/my-paper/figures/ \
  --assets    assets \
  --out       ./yomitoki-out/my-paper/ \
  --check
```

Open the resulting `yomitoki-out/my-paper/index.html` in a browser.

## Repository layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Skill definition and authoring workflow the agent follows. |
| `scripts/extract.py` | Paper extraction: text, figures, skeleton `analysis.json`. |
| `scripts/assemble.py` | HTML rendering and `--check` validation (stdlib only). |
| `references/authoring-guide.md` | `analysis.json` field contract and writing bar. |
| `references/code-ref-waterfall.md` | How to source and anchor code references. |
| `references/diagrams.md` | Figure curation and Mermaid safety. |
| `assets/` | `styles.css` and `main.js` copied into each note. |

## Requirements

- Python 3.10+
- `pypdf` and `pymupdf` (`pip install -r requirements.txt`)
- `pandoc` optional, for cleaner text extraction

## License

[MIT](LICENSE)
