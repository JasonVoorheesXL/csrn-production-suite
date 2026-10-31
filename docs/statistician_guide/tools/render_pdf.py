"""Render the statistician guide (guide_content.py + screenshots) to a CSRN-themed PDF.

Builds self-contained HTML and prints it with Playwright's Chromium (already a
project dependency), then joins the footer-less cover to the body with pypdf
(also already installed) -- no new PDF toolchain.

Output: static/guides/statistician-guide-football.pdf (shipped with the app; listed in guides_catalog.py)
        docs/statistician_guide/build/guide.html (the intermediate body HTML)
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

TOOLS = Path(__file__).resolve().parent
GUIDE = TOOLS.parent
REPO = GUIDE.parents[1]
SHOTS = GUIDE / "screenshots"
OUT_PDF = REPO / "static" / "guides" / "statistician-guide-football.pdf"
OUT_HTML = GUIDE / "build" / "guide.html"

sys.path.insert(0, str(TOOLS))
import guide_content as content  # noqa: E402

FIGURES: list[str] = []
KICKERS = {"0": "START HERE", "A": "APPENDIX"}


def data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def shot(slug: str) -> Path:
    matches = sorted(
        path for path in SHOTS.glob("*.png")
        if path.stem.split("_", 1)[0].isdigit() and path.stem.split("_", 1)[1] == slug
    )
    if not matches:
        raise SystemExit(f"Missing screenshot for '{slug}'")
    return matches[0]


def figure(slug: str, caption: str, size: str = "full") -> str:
    path = shot(slug)
    FIGURES.append(slug)
    return (
        f'<figure class="fig {size}"><div class="frame"><div class="frame-bar">'
        f'<span></span><span></span><span></span><em>STATISTICIAN CONSOLE</em></div>'
        f'<img src="{data_uri(path, "image/png")}"></div>'
        f'<figcaption><b>FIG {len(FIGURES)}</b> {caption}</figcaption></figure>'
    )


def render_block(block: tuple) -> str:
    kind = block[0]
    if kind == "section":
        _, number, title, lede = block
        kicker = KICKERS.get(number, f"PHASE {number}")
        return (
            f'<section class="opener"><div class="opener-num">{number}</div>'
            f'<div><div class="opener-kicker">{kicker}</div><h1>{title}</h1>'
            f'<p>{lede}</p></div></section>'
        )
    if kind in ("h2", "h3", "p"):
        return f"<{kind}>{block[1]}</{kind}>"
    if kind == "steps":
        return '<ol class="steps">' + "".join(f"<li>{step}</li>" for step in block[1]) + "</ol>"
    if kind == "bullets":
        return '<ul class="bullets">' + "".join(f"<li>{item}</li>" for item in block[1]) + "</ul>"
    if kind == "fields":
        rows = "".join(f"<tr><th>{name}</th><td>{desc}</td></tr>" for name, desc in block[1])
        return f'<table class="fields">{rows}</table>'
    if kind == "table":
        _, head, rows = block
        thead = "".join(f"<th>{cell}</th>" for cell in head)
        body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        return f'<table class="grid"><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>'
    if kind == "callout":
        _, tone, title, text = block
        return f'<aside class="callout {tone}"><div class="callout-title">{title}</div><div>{text}</div></aside>'
    if kind == "fig":
        return figure(*block[1:])
    if kind == "side":
        # A tall form screenshot beside its field-by-field explanation.
        _, slug, caption, inner = block
        right = "".join(render_block(b) for b in inner)
        return f'<div class="side">{figure(slug, caption, "side-fig")}<div class="side-text">{right}</div></div>'
    if kind == "pair":
        _, left, right = block
        return f'<div class="pair">{figure(*left, "half")}{figure(*right, "half")}</div>'
    if kind == "break":
        return '<div class="page-break"></div>'
    if kind == "keep":
        return '<div class="keep">' + "".join(render_block(b) for b in block[1]) + "</div>"
    raise ValueError(kind)


def stylesheet() -> str:
    fonts = REPO / "static" / "fonts"
    css = (TOOLS / "guide.css").read_text(encoding="utf-8")
    css = css.replace("{{MICHROMA}}", data_uri(fonts / "michroma-regular.woff2", "font/woff2"))
    return css.replace("{{KARANTINA}}", data_uri(fonts / "karantina-700.woff2", "font/woff2"))


def document(body: str, css: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>CSRN Statistician Guide — Football</title><style>{css}</style></head>"
        f"<body>{body}</body></html>"
    )


def cover_html(css: str) -> str:
    logo = data_uri(REPO / "static" / "csrn-logo.png", "image/png")
    return document(f"""
    <section class="cover">
      <div class="cover-stripe"></div>
      <img class="cover-logo" src="{logo}">
      <div class="cover-kicker">CSRN PRODUCTION SUITE · VOLUNTEER FIELD GUIDE</div>
      <h1 class="cover-title">STATISTICIAN<br><span>SCREEN</span></h1>
      <div class="cover-sport">FOOTBALL · GAME-DAY DATA ENTRY, PHASE BY PHASE</div>
      <p class="cover-lede">{content.COVER_LEDE}</p>
      <div class="cover-meta">{content.COVER_META}</div>
      <div class="cover-bottom"><span>CALEDONIA SPORTS RADIO NETWORK</span><span>ON AIR · ON THE RECORD</span></div>
    </section>""", css + "\n@page { margin: 0; }")


def body_html(css: str) -> str:
    toc = "".join(
        f'<li><span class="toc-num">{number}</span><span class="toc-title">{title}</span></li>'
        for number, title, _ in content.SECTIONS_INDEX
    )
    intro = "".join(render_block(b) for b in content.INTRO)
    body = "".join(render_block(b) for b in content.BODY)
    css = css.replace("@page :first { margin: 0; }", "")
    return document(
        f'<section class="toc-page"><div class="toc-kicker">IN THIS GUIDE</div>'
        f'<ol class="toc">{toc}</ol>{intro}</section><main>{body}</main>',
        css,
    )


FOOTER = """<div style="width:100%;font-family:Arial,sans-serif;font-size:7.5px;color:#6b7280;
  padding:0 0.55in;display:flex;justify-content:space-between;letter-spacing:.12em">
  <span><b style="color:#C9203B">CSRN</b> STATISTICIAN FIELD GUIDE · FOOTBALL</span>
  <span>FB-DEMO-GUIDE-001 · FICTIONAL DEMO DATA</span>
  <span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>"""


def main() -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    css = stylesheet()
    documents = {"cover": cover_html(css), "body": body_html(css)}
    OUT_HTML.write_text(documents["body"], encoding="utf-8")
    writer = PdfWriter()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for part, html_text in documents.items():
            page = browser.new_page()
            page.set_content(html_text, wait_until="load")
            page.wait_for_timeout(500)
            pdf = page.pdf(
                format="Letter",
                print_background=True,
                display_header_footer=part == "body",
                header_template="<span></span>",
                footer_template=FOOTER,
                prefer_css_page_size=True,
            )
            page.close()
            for pdf_page in PdfReader(io.BytesIO(pdf)).pages:
                writer.add_page(pdf_page)
        browser.close()
    writer.add_metadata({"/Title": "CSRN Statistician Field Guide — Football",
                         "/Author": "Caledonia Sports Radio Network"})
    with OUT_PDF.open("wb") as handle:
        writer.write(handle)
    print(f"Wrote {OUT_PDF} ({len(writer.pages)} pages, {len(FIGURES)} figures)")


if __name__ == "__main__":
    main()
