#!/usr/bin/env python3
"""
extract.py — paper-agnostic extractor for the yomitoki skill.

Usage:
    python extract.py <input> --out <dir> [--refresh] [--quiet]

<input> may be:
    - arXiv URL:   https://arxiv.org/abs/1706.03762
                   https://arxiv.org/html/1706.03762
    - arXiv ID:    1706.03762
    - Local PDF:   ./paper.pdf  or  /abs/path/paper.pdf
    - PDF URL:     https://example.com/paper.pdf

Outputs written to <out>/:
    raw.html          (arXiv inputs only) — raw HTML from arxiv.org/html
    extracted.txt     — clean markdown (pandoc) or plain-text (BS4/pypdf)
    figures/          (PDF inputs) — extracted raster + vector figures
    figures.json      — list of figure metadata
    analysis.json     — skeleton with title, authors, arxiv_id, sections, repo

Dependencies (install via pip):
    pypdf             (pip install pypdf)
    pymupdf           (pip install pymupdf)     — figure extraction from PDF
    beautifulsoup4    (pip install beautifulsoup4)
    pandoc            (apt install pandoc)      — optional; BS4 fallback used if absent
    curl              — required for downloading files
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

# ── Constants ─────────────────────────────────────────────────────────────────

ARXIV_HTML_BASE = "https://arxiv.org/html"
AR5IV_BASE = "https://ar5iv.labs.arxiv.org/html"
ARXIV_PDF_BASE = "https://arxiv.org/pdf"

# Repos to skip when detecting the "author repo"
INFRA_REPO_BLOCKLIST = {
    "LaTeXML", "arxiv", "brucemiller", "html_feedback",
    "arXiv", "latex3", "arXivLabs", "dginev",
}

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?$")
ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|html|pdf)/(\d{4}\.\d{4,5})(v\d+)?"
)
GITHUB_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)"
)
HF_RE = re.compile(
    r"https?://huggingface\.co/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)"
)
# Hugging Face namespaces that are never a model/code repo.
HF_NAMESPACE_BLOCKLIST = {
    "datasets", "blog", "docs", "papers", "spaces", "collections", "organizations",
}
# Words that, just before a repo URL, mark it as the paper's own released code.
CODE_PROXIMITY_RE = re.compile(
    r"(open[- ]?source|implementation|available at|released?|reproduce|"
    r"our (?:code|model|implementation)|project page|\bcode\b)",
    re.I,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg, flush=True)


def run(cmd: list[str], check: bool = True, capture: bool = False):
    """Run a subprocess command."""
    kwargs = dict(check=check)
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def curl_download(url: str, dest: Path, quiet: bool = False):
    """Download URL to dest using curl."""
    cmd = ["curl", "-fL", "--silent" if quiet else "--progress-bar",
           "-o", str(dest), url]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed (rc={result.returncode}) for {url}")


def _repo_context_score(text: str, pos: int) -> int:
    """Score a repo URL by how strongly the preceding text (a 120-char
    lookbehind) marks it as the authors' own released code."""
    window = text[max(0, pos - 120):pos]
    return len(CODE_PROXIMITY_RE.findall(window))


def detect_author_repo(text: str) -> str | None:
    """Find the paper's own code repo (GitHub or Hugging Face).

    Collect every credible candidate URL, then prefer the one whose preceding
    context mentions code / open-source / implementation; break ties by
    earliest appearance. This beats 'first GitHub URL in reading order', which
    often grabs a citation or an infra link instead of the authors' release,
    and it can surface Hugging Face repos for models that ship code there.
    """
    candidates = []  # (score, position, url)
    for m in GITHUB_RE.finditer(text):
        owner, repo = m.group(1), m.group(2)
        if owner in INFRA_REPO_BLOCKLIST:
            continue
        if repo in ("html_feedback", "LaTeXML"):
            continue
        if repo.lower() in ("arxiv", "latex", "paper", "template"):
            continue
        candidates.append((_repo_context_score(text, m.start()), m.start(),
                           f"https://github.com/{owner}/{repo}"))
    for m in HF_RE.finditer(text):
        owner, repo = m.group(1), m.group(2)
        if owner.lower() in HF_NAMESPACE_BLOCKLIST:
            continue
        candidates.append((_repo_context_score(text, m.start()), m.start(),
                           f"https://huggingface.co/{owner}/{repo}"))
    if not candidates:
        return None
    # Highest context score wins; ties broken by earliest appearance.
    candidates.sort(key=lambda c: (-c[0], c[1]))
    return candidates[0][2]


def parse_input(inp: str) -> tuple[str, str | None, str | None]:
    """
    Returns (kind, arxiv_id, url_or_path).
    kind ∈ {'arxiv', 'pdf_url', 'pdf_local'}
    """
    # arXiv URL
    m = ARXIV_URL_RE.search(inp)
    if m:
        return "arxiv", m.group(1), None

    # arXiv bare ID
    m = ARXIV_ID_RE.match(inp)
    if m:
        return "arxiv", m.group(1), None

    # PDF URL
    if inp.startswith("http://") or inp.startswith("https://"):
        return "pdf_url", None, inp

    # Local path
    p = Path(inp).expanduser().resolve()
    return "pdf_local", None, str(p)


# ── arXiv HTML path ───────────────────────────────────────────────────────────

def fetch_arxiv_html(arxiv_id: str, out_dir: Path, refresh: bool, quiet: bool) -> Path:
    """Download arxiv.org/html/<id>, fall back to ar5iv. Returns path to raw.html."""
    raw_html = out_dir / "raw.html"
    if raw_html.exists() and not refresh:
        log(f"  raw.html cached, skipping fetch", quiet)
        return raw_html

    primary_url = f"{ARXIV_HTML_BASE}/{arxiv_id}"
    fallback_url = f"{AR5IV_BASE}/{arxiv_id}"

    # Try primary
    log(f"  Fetching {primary_url} ...", quiet)
    try:
        curl_download(primary_url, raw_html, quiet=quiet)
        # Check for 404-type empty / redirect pages
        content = raw_html.read_text(errors="replace")
        if len(content) < 2000 or "404" in content[:500]:
            raise RuntimeError("looks like a 404")
        log(f"  Downloaded {raw_html.stat().st_size // 1024} KB from arxiv.org/html", quiet)
        return raw_html
    except RuntimeError:
        log(f"  Primary failed, trying ar5iv fallback ...", quiet)

    try:
        curl_download(fallback_url, raw_html, quiet=quiet)
        content = raw_html.read_text(errors="replace")
        if len(content) < 2000:
            raise RuntimeError("ar5iv also empty")
        log(f"  Downloaded {raw_html.stat().st_size // 1024} KB from ar5iv", quiet)
        return raw_html
    except RuntimeError:
        log("  Both HTML mirrors failed — will fall back to PDF", quiet)
        raw_html.unlink(missing_ok=True)
        raise RuntimeError(f"No HTML mirror available for {arxiv_id}")


_BACK_MATTER_RE = re.compile(
    r"^#{1,6}[ \t]*\d*\.?[ \t]*(references|bibliography|acknowledge?ments?)\b.*",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def _strip_back_matter(text: str) -> str:
    """Drop the references / bibliography / acknowledgments tail (and anything
    after it). It's never needed to author the note and is often 20-40% of the
    paper's text — pure input-token savings each run."""
    m = _BACK_MATTER_RE.search(text)
    return (text[:m.start()].rstrip() + "\n") if m else text


def html_to_markdown_pandoc(html_path: Path, out_dir: Path, quiet: bool) -> Path:
    """Convert raw.html → extracted.txt via pandoc (gfm-raw_html)."""
    txt_path = out_dir / "extracted.txt"
    cmd = [
        "pandoc",
        "-f", "html",
        "-t", "gfm-raw_html",
        "--wrap=none",
        "-o", str(txt_path),
        str(html_path),
    ]
    log("  Converting HTML → markdown via pandoc ...", quiet)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed: {result.stderr[:300]}")
    txt_path.write_text(_strip_back_matter(txt_path.read_text(errors="replace")))
    log(f"  extracted.txt: {txt_path.stat().st_size // 1024} KB", quiet)
    return txt_path


def html_to_text_bs4(html_path: Path, out_dir: Path, quiet: bool) -> Path:
    """BS4 fallback: strip nav/header, extract article body as plain text."""
    from bs4 import BeautifulSoup

    log("  Converting HTML → text via BeautifulSoup (pandoc not available) ...", quiet)
    soup = BeautifulSoup(html_path.read_text(errors="replace"), "html.parser")

    # Remove noisy nav elements
    for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
        tag.decompose()

    article = soup.find("article") or soup.find("div", id="content") or soup.body or soup
    txt_path = out_dir / "extracted.txt"
    txt_path.write_text(_strip_back_matter(article.get_text(separator="\n", strip=True)))
    log(f"  extracted.txt: {txt_path.stat().st_size // 1024} KB", quiet)
    return txt_path


def _derive_html_base_url(soup, arxiv_id: str) -> str:
    """Find the actual page URL so relative <img src> resolves correctly.

    arXiv HTML pages live at https://arxiv.org/html/<id>v<N>/, and <img>s are
    typically bare filenames like 'x1.png' relative to that. Earlier versions
    of this script built 'https://arxiv.org/html/x1.png' (no <id>v<N>/), which
    404s.

    Resolution order:
      1. <base href="..."> — authoritative if present.
      2. <link rel="canonical"> — usually /abs/<id>v<N>; rewrite /abs/ → /html/.
      3. <meta property="og:url"> — same shape as canonical.
      4. Fall back to https://arxiv.org/html/<id>/ (no version; usually redirects).
    """
    def _absolutize(href: str) -> str:
        """Promote a path-only URL to https://arxiv.org/... so urljoin works."""
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return "https://arxiv.org" + href
        return href

    base_tag = soup.find("base")
    if base_tag and base_tag.get("href"):
        href = _absolutize(base_tag["href"])
        return href if href.endswith("/") else href + "/"

    for selector in (
        ("link", {"rel": "canonical"}),
        ("meta", {"property": "og:url"}),
    ):
        tag = soup.find(*selector[:1], attrs=selector[1])
        if not tag:
            continue
        href = tag.get("href") or tag.get("content")
        if not href:
            continue
        href = _absolutize(href)
        href = href.replace("/abs/", "/html/").replace("/pdf/", "/html/")
        if href.endswith(".pdf"):
            href = href[:-4]
        return href if href.endswith("/") else href + "/"

    return f"{ARXIV_HTML_BASE}/{arxiv_id}/"


def _download_arxiv_figure(abs_url: str, dest_dir: Path, quiet: bool) -> Path | None:
    """Download one figure; return the local Path on success, else None.

    Skips static assets like the arXiv logo (under /static/). Uses the URL's
    basename as the local filename; collisions across pages are unlikely on
    arXiv (figures are usually x1.png, x2.png, ...).
    """
    parsed = urlparse(abs_url)
    if parsed.path.startswith("/static/"):
        return None
    fname = Path(parsed.path).name or "figure.png"
    dest = dest_dir / fname
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        curl_download(abs_url, dest, quiet=True)
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            return None
        return dest
    except Exception as e:
        log(f"  [warn] failed to download {abs_url}: {e}", quiet)
        dest.unlink(missing_ok=True)
        return None


def extract_figures_arxiv(html_path: Path, arxiv_id: str, out_dir: Path, quiet: bool) -> list[dict]:
    """Parse <img> tags, resolve URLs against the page base, download them.

    Writes images into <out_dir>/figures/. Returns a list of dicts with both
    the remote URL and the local path so downstream tools can pick either.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_path.read_text(errors="replace"), "html.parser")
    base_url = _derive_html_base_url(soup, arxiv_id)
    log(f"  Resolving <img> srcs against base: {base_url}", quiet)

    figs_dir = out_dir / "figures"
    figs_dir.mkdir(exist_ok=True)

    figures = []
    seen_srcs = set()

    article = soup.find("article") or soup.body or soup
    img_tags = list(article.find_all("img"))
    log(f"  Detected {len(img_tags)} <img> tags in HTML; downloading ...", quiet)

    for img in img_tags:
        src = (img.get("src") or "").strip()
        if not src or src in seen_srcs:
            continue
        seen_srcs.add(src)

        if src.startswith("http://") or src.startswith("https://"):
            abs_src = src
        elif src.startswith("//"):
            abs_src = "https:" + src
        elif src.startswith("/"):
            abs_src = "https://arxiv.org" + src
        else:
            abs_src = urljoin(base_url, src)

        # Try to find the enclosing figure + figcaption
        figure_tag = img.find_parent("figure")
        caption = ""
        if figure_tag:
            figcap = figure_tag.find("figcaption")
            if figcap:
                caption = figcap.get_text(strip=True)[:300]

        # Rough page estimate from section proximity
        section = img.find_parent(lambda t: t.name == "section" and t.get("id"))
        page_hint = None
        if section:
            sec_id = section.get("id", "")
            m = re.match(r"S(\d+)", sec_id)
            if m:
                page_hint = int(m.group(1))

        local = _download_arxiv_figure(abs_src, figs_dir, quiet)
        entry = {
            "src": abs_src,
            "caption": caption,
            "page": page_hint,
        }
        if local is not None:
            # The path field is what assembled HTML actually references.
            entry["path"] = f"figures/{local.name}"
        figures.append(entry)

    downloaded = sum(1 for f in figures if "path" in f)
    log(f"  Downloaded {downloaded}/{len(figures)} figures into figures/", quiet)
    if img_tags and downloaded == 0:
        # Hard precondition: the HTML claimed figures but we got nothing on disk.
        # The note can't be authored without them. Caller decides whether to
        # fall back to PDF extraction.
        raise RuntimeError(
            f"extract_figures_arxiv: HTML had {len(img_tags)} <img> tags but "
            f"downloaded 0 figures. URL resolution likely broken; base_url={base_url!r}."
        )
    return figures


def parse_sections_arxiv(html_path: Path) -> list[dict]:
    """Extract sections from arXiv ltx_section tags."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_path.read_text(errors="replace"), "html.parser")
    sections = []

    for sec in soup.find_all("section"):
        sec_id = sec.get("id", "")
        if not re.match(r"^[SA]\d", sec_id):
            continue
        # Heading
        h = sec.find(re.compile(r"^h[1-6]$"))
        heading_text = h.get_text(strip=True) if h else sec_id
        # Level from tag
        level = int(h.name[1]) if h else 1
        sections.append({"id": sec_id, "heading": heading_text, "level": level})

    # Deduplicate, preserve order
    seen = set()
    deduped = []
    for s in sections:
        if s["id"] not in seen:
            seen.add(s["id"])
            deduped.append(s)
    return deduped


def extract_title_authors_arxiv(html_path: Path) -> tuple[str, str]:
    """Best-effort title + authors from arXiv HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_path.read_text(errors="replace"), "html.parser")

    # Title: prefer og:title meta, then <title>, then first h1
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    else:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        # Strip " - arXiv" suffix
        title = re.sub(r"\s*[-–]\s*arXiv.*$", "", title, flags=re.IGNORECASE)

    # Authors: look for ltx_authors or author meta
    meta_author = soup.find("meta", attrs={"name": "citation_author"})
    author_tags = soup.find_all("meta", attrs={"name": "citation_author"})
    if author_tags:
        authors = ", ".join(a.get("content", "") for a in author_tags[:6])
        if len(author_tags) > 6:
            authors += " et al."
    else:
        auth_div = soup.find(class_=re.compile(r"ltx_authors?|authors?"))
        authors = auth_div.get_text(strip=True)[:200] if auth_div else ""

    return title, authors


# ── PDF path ──────────────────────────────────────────────────────────────────

def ensure_pdf(out_dir: Path, pdf_url: str | None, pdf_local: str | None,
               refresh: bool, quiet: bool) -> Path:
    """Return path to <out>/paper.pdf, downloading or symlinking as needed."""
    dest = out_dir / "paper.pdf"

    if dest.exists() and not refresh:
        log("  paper.pdf cached", quiet)
        return dest

    if pdf_url:
        log(f"  Downloading PDF from {pdf_url} ...", quiet)
        curl_download(pdf_url, dest, quiet=quiet)
    elif pdf_local:
        src = Path(pdf_local)
        if not src.exists():
            raise FileNotFoundError(f"Local PDF not found: {src}")
        if dest.exists():
            dest.unlink()
        # Symlink if on same filesystem, else copy
        try:
            dest.symlink_to(src)
            log(f"  Symlinked {src} -> {dest}", quiet)
        except OSError:
            shutil.copy2(src, dest)
            log(f"  Copied {src} -> {dest}", quiet)
    else:
        raise ValueError("No PDF source provided")

    return dest


def read_pdf_metadata(pdf_path: Path) -> tuple[str, str]:
    """Read embedded /Title and /Author from the PDF document info.

    When present and not exporter junk, this is far more reliable than parsing
    the first page, so callers should prefer it and fall back to the text
    heuristic only for missing fields.
    """
    try:
        import pypdf
    except ImportError:
        return "", ""
    try:
        with open(pdf_path, "rb") as f:
            meta = pypdf.PdfReader(f).metadata or {}
    except Exception:
        return "", ""

    def _clean(v):
        return re.sub(r"\s+", " ", str(v)).strip() if v else ""

    title = _clean(meta.get("/Title"))
    author = _clean(meta.get("/Author"))
    low = title.lower()
    if (low in ("untitled", "microsoft word", "paper", "main", "manuscript", "arxiv")
            or low.endswith((".dvi", ".tex", ".doc", ".docx", ".pdf"))
            or len(title) < 6):
        title = ""
    if len(author) < 2:
        author = ""
    return title, author


def extract_text_pypdf(pdf_path: Path, out_dir: Path, quiet: bool) -> Path:
    """Extract text from PDF using pypdf; saves as extracted.txt."""
    try:
        import pypdf
    except ImportError:
        raise ImportError("pypdf not installed: pip install pypdf")

    log("  Extracting text with pypdf ...", quiet)
    txt_path = out_dir / "extracted.txt"
    lines = []

    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for i, page in enumerate(reader.pages):
            lines.append(f"===== PAGE {i+1} =====")
            try:
                lines.append(page.extract_text() or "")
            except Exception as e:
                lines.append(f"[extraction error: {e}]")

    txt_path.write_text(_strip_back_matter("\n".join(lines)))
    log(f"  extracted.txt: {txt_path.stat().st_size // 1024} KB, {len(reader.pages)} pages", quiet)
    return txt_path


def _expand_cluster_with_text(page, rect, blocks):
    """Grow a vector-drawing cluster to include its axis labels + caption.

    `cluster_drawings()` bounds only drawing operators, so for a pgfplots/TikZ
    chart the tick labels, axis titles, legend text and the "Figure N:" caption
    (all *text*, not drawings) fall outside the cluster — rendering it produces
    a plot stripped of every label. We union nearby text back in, but skip
    body-prose paragraphs so we don't slurp the paragraph above the figure.

    Returns (expanded_rect, caption_str).
    """
    import fitz
    # Directional halos (points). Labels hug the plot on the sides; the caption
    # and x-axis title sit below; body prose sits above, so keep the top tight.
    L, R, T, B = 85, 85, 24, 78
    halo = fitz.Rect(rect.x0 - L, rect.y0 - T, rect.x1 + R, rect.y1 + B)
    page_w = page.rect.width
    fig = +rect
    caption = ""
    for b in blocks:
        if len(b) < 7 or b[6] != 0:           # 0 == text block (skip image blocks)
            continue
        bx = fitz.Rect(b[:4])
        txt = (b[4] or "").strip()
        if not txt:
            continue
        # The caption: a "Figure N" / "Table N" line just below the cluster.
        is_caption = (
            re.match(r"^(figure|table|fig\.)\s*\d", txt, re.I)
            and rect.y1 - 5 <= bx.y0 <= rect.y1 + B
        )
        if is_caption:
            fig |= bx
            if not caption:
                caption = " ".join(txt.split())
            continue
        if not bx.intersects(halo):
            continue
        # Skip body-prose paragraphs: axis tick labels, rotated axis titles and
        # legend text are all narrow, so a wide block near the figure is almost
        # always the paragraph above/below it (the caption is handled above).
        if bx.width > 0.55 * page_w:
            continue
        fig |= bx
    fig &= page.rect                          # clamp to page bounds
    return fig, caption


def extract_figures_pdf(pdf_path: Path, out_dir: Path, quiet: bool) -> list[dict]:
    """
    Extract figures from PDF via PyMuPDF.
    Two methods:
      1. page.get_images()  — embedded raster images (dedupe by hash, skip small)
      2. page.cluster_drawings() — vector figure regions rendered via get_pixmap()
    """
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF not installed: pip install pymupdf")

    figs_dir = out_dir / "figures"
    figs_dir.mkdir(exist_ok=True)

    figures = []
    seen_hashes = set()

    doc = fitz.open(str(pdf_path))
    log(f"  Extracting figures from {len(doc)} page PDF ...", quiet)

    for page_num, page in enumerate(doc):
        page_label = f"p{page_num+1:02d}"

        # ── Method 1: embedded raster images ──────────────────────────────────
        raster_idx = 0
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_w = base_image.get("width", 0)
                img_h = base_image.get("height", 0)
                ext = base_image.get("ext", "png")
            except Exception:
                continue

            # Skip tiny images (icons, bullets, logos)
            if img_w < 80 or img_h < 80:
                continue

            # Deduplicate by content hash
            h = hashlib.md5(img_bytes).hexdigest()[:10]
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            fname = f"{page_label}_raster_{raster_idx:02d}_{h}.png"
            out_path = figs_dir / fname
            # Save as PNG (convert if needed)
            try:
                pix = fitz.Pixmap(img_bytes)
                if pix.colorspace and pix.colorspace.name not in ("DeviceRGB", "DeviceGray"):
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                pix.save(str(out_path))
            except Exception:
                # Fallback: write raw bytes
                out_path.write_bytes(img_bytes)

            figures.append({
                "path": f"figures/{fname}",
                "page": page_num + 1,
                "kind": "raster",
                "width": img_w,
                "height": img_h,
                "bbox": None,
            })
            raster_idx += 1

        # ── Method 2: vector figure clusters (cluster_drawings) ───────────────
        MIN_DIM_PT = 100  # points — skip tiny clusters (rules, borders)
        SCALE = 150 / 72  # 150 DPI rendering

        try:
            clusters = page.cluster_drawings(x_tolerance=3, y_tolerance=3)
        except Exception:
            clusters = []

        # Text blocks once per page, reused to re-attach labels/captions below.
        try:
            text_blocks = page.get_text("blocks")
        except Exception:
            text_blocks = []

        for vec_idx, rect in enumerate(clusters):
            if rect.width < MIN_DIM_PT or rect.height < MIN_DIM_PT:
                continue

            # Re-attach the chart's text (axis labels, legend, caption) that
            # cluster_drawings leaves out, so the crop isn't a label-less plot.
            fig_rect, caption = _expand_cluster_with_text(page, rect, text_blocks)

            try:
                mat = fitz.Matrix(SCALE, SCALE)
                pix = page.get_pixmap(clip=fig_rect, matrix=mat, alpha=False)
                raw_bytes = pix.tobytes("png")
            except Exception:
                continue

            # Deduplicate
            h = hashlib.md5(raw_bytes).hexdigest()[:10]
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            fname = f"{page_label}_vector_{vec_idx:02d}_{h}.png"
            out_path = figs_dir / fname
            out_path.write_bytes(raw_bytes)

            figures.append({
                "path": f"figures/{fname}",
                "page": page_num + 1,
                "kind": "vector",
                "caption": caption,
                "width": round(fig_rect.width),
                "height": round(fig_rect.height),
                "bbox": [round(fig_rect.x0), round(fig_rect.y0),
                         round(fig_rect.x1), round(fig_rect.y1)],
            })

    doc.close()
    n_raster = sum(1 for f in figures if f["kind"] == "raster")
    n_vector = sum(1 for f in figures if f["kind"] == "vector")
    log(f"  Figures: {n_raster} raster, {n_vector} vector → {len(figures)} total", quiet)
    return figures


def parse_sections_pdf(txt_path: Path) -> list[dict]:
    """Regex-scan extracted.txt for section headings.

    Top-level: integer 1-99 + whitespace + capitalized word sequence.
    Subsection: N.N pattern.
    Requires the section number to be 1-2 digits (not 0.x decimals) to
    avoid matching table numbers and chart values.
    """
    text = txt_path.read_text(errors="replace")
    sections = []
    seen = set()

    # Top-level sections: "1 Introduction", "2 Model" etc.
    # Heading must start with a capital letter and contain only word chars + spaces.
    # Use strict word-boundary (\b) so "10 " doesn't match "0.10 " in table context.
    top_level = re.compile(
        r"^([1-9]\d?)\s{1,4}([A-Z][A-Za-z][A-Za-z0-9\s\-:&]{1,55})$",
        re.MULTILINE,
    )
    sub_level = re.compile(
        r"^([1-9]\d?\.\d{1,2})\s{1,4}([A-Z][A-Za-z].{1,60})$",
        re.MULTILINE,
    )

    for m in top_level.finditer(text):
        num, heading = m.group(1), m.group(2).strip()
        # Reject if heading looks like a number-heavy table row
        if re.search(r"\d{2,}", heading):
            continue
        # Reject very short headings that are likely noise
        if len(heading) < 3:
            continue
        sec_id = f"S{num}"
        if sec_id in seen:
            continue
        seen.add(sec_id)
        sections.append({"id": sec_id, "heading": f"{num} {heading}", "level": 1})

    for m in sub_level.finditer(text):
        num, heading = m.group(1), m.group(2).strip()
        if re.search(r"\d{4,}", heading):
            continue
        sec_id = f"S{num.replace('.', '_')}"
        if sec_id in seen:
            continue
        seen.add(sec_id)
        sections.append({"id": sec_id, "heading": f"{num} {heading}", "level": 2})

    # Sort by numeric section id
    def sec_sort_key(s):
        m = re.match(r"S(\d+)(?:_(\d+))?", s["id"])
        if m:
            return (int(m.group(1)), int(m.group(2) or 0))
        return (999, 0)

    sections.sort(key=sec_sort_key)
    return sections


# Trailing tokens/punctuation that mark a wrapped (continued) title line.
_TITLE_CONNECTIVE_RE = re.compile(
    r"([:,\-]|\b(?:and|or|of|for|the|a|an|to|with|on|in|via|using|towards?|from|by))$",
    re.I,
)
# Signals that a line is an author/affiliation/section start, not a title line.
_NON_TITLE_RE = re.compile(
    r"@|\b(universit|institut|laborator|abstract|introduction|keywords|contents|"
    r"deepmind|openai|microsoft|nvidia|anthropic)\b",
    re.I,
)
# Lines short enough to fail the length guard but acceptable as an org byline.
_ORG_AUTHOR_RE = re.compile(
    r"(-?AI\b|Labs?\b|Research\b|Team\b|Institute\b|University\b|DeepMind|OpenAI|"
    r"Google|Microsoft|NVIDIA|Meta|Anthropic)",
)


def extract_title_authors_pdf(txt_path: Path) -> tuple[str, str]:
    """Best-effort title/author from the first page of extracted.txt.

    Handles titles that wrap across several lines (joined while a line ends in a
    connective and the next is not an author/affiliation), and recognizes
    organization bylines and email lines so an author is not swallowed into the
    title. Embedded PDF metadata (read_pdf_metadata) should be preferred when
    available; this is the fallback.
    """
    text = txt_path.read_text(errors="replace")
    # First 3000 chars usually contain title/authors before the first section.
    head = text[:3000]
    lines = [l.strip() for l in head.split("\n") if l.strip()]

    # Skip page markers and obvious noise.
    filtered = []
    for l in lines:
        if re.match(r"^=====", l):
            continue
        # Skip date-looking lines (e.g. "August 4, 2025").
        if re.match(r"^[A-Z][a-z]+ \d+, \d{4}$", l):
            continue
        # Skip URL lines.
        if l.startswith("http://") or l.startswith("https://"):
            continue
        # Skip lines that are mostly digits/symbols (chart data leaking in).
        digit_ratio = sum(1 for c in l if c.isdigit()) / max(len(l), 1)
        if digit_ratio > 0.4 and len(l) < 40:
            continue
        filtered.append(l)

    if not filtered:
        return "", ""

    # Assemble a possibly multi-line title: keep joining while the last line
    # ends in a connective and the next line is not an author/affiliation.
    title_lines = [filtered[0]]
    i = 1
    while (i < len(filtered)
           and _TITLE_CONNECTIVE_RE.search(title_lines[-1])
           and not _NON_TITLE_RE.search(filtered[i])):
        title_lines.append(filtered[i])
        i += 1
    title = " ".join(title_lines)

    # The next line after the title is the best author candidate.
    authors = filtered[i] if i < len(filtered) else ""
    if "@" in authors:                                   # email line, not a byline
        authors = ""
    elif re.match(r"^[\d\s.,/()-]+$", authors):          # coordinate/numeric noise
        authors = ""
    elif len(authors) < 4 and not _ORG_AUTHOR_RE.search(authors):
        authors = ""

    return title, authors


# ── arXiv → PDF fallback ──────────────────────────────────────────────────────

def handle_arxiv(arxiv_id: str, out_dir: Path, refresh: bool, quiet: bool):
    """Full arXiv pipeline. May fall back to PDF if HTML unavailable."""
    log(f"  arXiv ID: {arxiv_id}", quiet)

    try:
        html_path = fetch_arxiv_html(arxiv_id, out_dir, refresh, quiet)
        # HTML path
        txt_path = _convert_html(html_path, out_dir, quiet)
        try:
            figures = extract_figures_arxiv(html_path, arxiv_id, out_dir, quiet)
        except RuntimeError as e:
            # Download bug, broken base URL, etc. Don't silently move on; fall
            # back to the PDF figure extractor below.
            log(f"  [warn] HTML figure pass failed: {e}", quiet)
            figures = []

        # Edge case: LaTeXML/ar5iv renders pgfplots/TikZ charts as inline SVG or
        # text, not <img>, so the HTML scrape can find 0 figures even when the
        # paper clearly has them. Fall back to the PDF figure extractor (the PDF
        # is fetched anyway, below) so vector charts aren't silently dropped.
        if not figures:
            log("  HTML yielded 0 figures; falling back to PDF figure extraction ...", quiet)
            try:
                pdf_path = ensure_pdf(out_dir, f"{ARXIV_PDF_BASE}/{arxiv_id}",
                                      None, refresh, quiet)
                figures = extract_figures_pdf(pdf_path, out_dir, quiet)
            except Exception as e:
                log(f"  [warn] PDF figure fallback failed: {e}", quiet)

        figs_json = out_dir / "figures.json"
        figs_json.write_text(json.dumps(figures, indent=2, ensure_ascii=False))
        log(f"  figures.json: {len(figures)} entries", quiet)

        title, authors = extract_title_authors_arxiv(html_path)
        sections = parse_sections_arxiv(html_path)

    except RuntimeError:
        log("  Falling back to PDF extraction ...", quiet)
        pdf_url = f"{ARXIV_PDF_BASE}/{arxiv_id}"
        pdf_path = ensure_pdf(out_dir, pdf_url, None, refresh, quiet)
        txt_path = extract_text_pypdf(pdf_path, out_dir, quiet)
        figures = extract_figures_pdf(pdf_path, out_dir, quiet)
        figs_json = out_dir / "figures.json"
        figs_json.write_text(json.dumps(figures, indent=2, ensure_ascii=False))
        meta_title, meta_authors = read_pdf_metadata(pdf_path)
        text_title, text_authors = extract_title_authors_pdf(txt_path)
        title = meta_title or text_title
        authors = meta_authors or text_authors
        sections = parse_sections_pdf(txt_path)

    # Keep the original paper alongside the note (the HTML path skips the PDF; fetch it once).
    if not (out_dir / "paper.pdf").exists():
        try:
            ensure_pdf(out_dir, f"{ARXIV_PDF_BASE}/{arxiv_id}", None, refresh, quiet)
        except Exception as e:
            log(f"  [warn] could not fetch original paper.pdf: {e}", quiet)

    # Author repo detection
    extracted_text = (out_dir / "extracted.txt").read_text(errors="replace")
    author_repo = detect_author_repo(extracted_text)

    analysis = {
        "title": title,
        "authors": authors or None,
        "arxiv_id": arxiv_id,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
        "author_repo": author_repo,
        "sections": sections,
    }
    (out_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False)
    )
    log(f"  analysis.json written ({len(sections)} sections)", quiet)
    log("  [verify] title, authors, and author_repo are best-effort guesses; "
        "confirm them against the paper before authoring.", quiet)
    return analysis


def _convert_html(html_path: Path, out_dir: Path, quiet: bool) -> Path:
    """Convert html → extracted.txt via pandoc or BS4 fallback."""
    if shutil.which("pandoc"):
        return html_to_markdown_pandoc(html_path, out_dir, quiet)
    else:
        return html_to_text_bs4(html_path, out_dir, quiet)


def handle_pdf(pdf_path_or_url: str, is_url: bool, out_dir: Path,
               refresh: bool, quiet: bool):
    """Full PDF pipeline."""
    if is_url:
        pdf_path = ensure_pdf(out_dir, pdf_path_or_url, None, refresh, quiet)
    else:
        pdf_path = ensure_pdf(out_dir, None, pdf_path_or_url, refresh, quiet)

    # Text extraction
    try:
        txt_path = extract_text_pypdf(pdf_path, out_dir, quiet)
    except ImportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Figure extraction
    try:
        figures = extract_figures_pdf(pdf_path, out_dir, quiet)
    except ImportError as e:
        print(f"WARNING: PyMuPDF not available — skipping figure extraction: {e}", file=sys.stderr)
        figures = []

    figs_json = out_dir / "figures.json"
    figs_json.write_text(json.dumps(figures, indent=2, ensure_ascii=False))
    log(f"  figures.json: {len(figures)} entries", quiet)

    # Prefer embedded PDF metadata (usually exact); fall back to first-page text.
    meta_title, meta_authors = read_pdf_metadata(pdf_path)
    text_title, text_authors = extract_title_authors_pdf(txt_path)
    title = meta_title or text_title
    authors = meta_authors or text_authors
    sections = parse_sections_pdf(txt_path)
    extracted_text = txt_path.read_text(errors="replace")
    author_repo = detect_author_repo(extracted_text)

    # Paper URL
    if is_url:
        paper_url = pdf_path_or_url
    else:
        paper_url = f"file://{out_dir / 'paper.pdf'}"

    analysis = {
        "title": title,
        "authors": authors or None,
        "arxiv_id": None,
        "arxiv_url": None,
        "paper_url": paper_url,
        "author_repo": author_repo,
        "sections": sections,
    }
    (out_dir / "analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False)
    )
    log(f"  analysis.json written ({len(sections)} sections)", quiet)
    log("  [verify] title, authors, and author_repo are best-effort guesses; "
        "confirm them against the paper before authoring.", quiet)
    return analysis


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract a paper (arXiv or PDF) into yomitoki-ready files."
    )
    parser.add_argument("input", help="arXiv URL/ID, local PDF path, or PDF URL")
    parser.add_argument("--out", required=True, metavar="DIR",
                        help="Output directory (created if needed)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-fetch even if cache exists")
    parser.add_argument("--quiet", action="store_true",
                        help="Minimal stdout")
    args = parser.parse_args()

    out_dir = Path(args.out)
    # Guardrail: writing to bare /tmp/yomitoki/ would overwrite a previous
    # paper's artifacts. Force the caller to pass a slug subfolder.
    if out_dir.resolve() == Path("/tmp/yomitoki").resolve():
        sys.exit(
            "ERROR: --out is the bare base /tmp/yomitoki/. "
            "Pass --out /tmp/yomitoki/<paper-slug>/ instead "
            "(slug = lowercased, hyphenated first 4 words of the paper title)."
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    kind, arxiv_id, url_or_path = parse_input(args.input)

    log(f"[extract.py] input={args.input!r}  kind={kind}  out={out_dir}", args.quiet)

    if kind == "arxiv":
        analysis = handle_arxiv(arxiv_id, out_dir, args.refresh, args.quiet)
    elif kind == "pdf_url":
        analysis = handle_pdf(url_or_path, True, out_dir, args.refresh, args.quiet)
    elif kind == "pdf_local":
        analysis = handle_pdf(url_or_path, False, out_dir, args.refresh, args.quiet)
    else:
        print(f"ERROR: Unrecognized input type: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Summary
    log("", args.quiet)
    log(f"Done. Output in: {out_dir}", args.quiet)
    log(f"  title:       {analysis.get('title', '')[:80]}", args.quiet)
    log(f"  authors:     {(analysis.get('authors') or '')[:60]}", args.quiet)
    log(f"  sections:    {len(analysis.get('sections', []))}", args.quiet)
    log(f"  author_repo: {analysis.get('author_repo')}", args.quiet)
    files = sorted(out_dir.rglob("*"))
    log(f"  files:       {[str(f.relative_to(out_dir)) for f in files if f.is_file()]}", args.quiet)


if __name__ == "__main__":
    main()
