from __future__ import annotations

from datetime import datetime
from html import escape

from epub_summarizer.models import ChapterSummary


def render_report(
    *,
    book_title: str,
    source_file_name: str,
    model_name: str,
    chapters: list[ChapterSummary],
    status_message: str | None = None,
) -> str:
    chapter_sections = "\n".join(
        _render_chapter_section(index=index, chapter=chapter)
        for index, chapter in enumerate(chapters, start=1)
    )
    empty_state = (
        '<p class="empty-state">No chapter summaries are available in this report.</p>'
        if not chapters
        else ""
    )
    status_markup = (
        f'<p class="status">{escape(status_message)}</p>'
        if status_message
        else ""
    )
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(book_title)} summary</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f1e8;
      --surface: rgba(255, 255, 255, 0.9);
      --surface-strong: #fffdf8;
      --text: #1f1b16;
      --muted: #74685b;
      --border: rgba(91, 74, 56, 0.18);
      --accent: #8b4a24;
      --accent-soft: rgba(139, 74, 36, 0.12);
      --shadow: 0 18px 60px rgba(52, 39, 25, 0.08);
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-size: 18px;
      line-height: 1.65;
      background:
        radial-gradient(circle at top left, rgba(214, 172, 111, 0.35), transparent 30%),
        radial-gradient(circle at bottom right, rgba(139, 74, 36, 0.18), transparent 30%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
    }}

    main {{
      width: min(980px, calc(100vw - 32px));
      margin: 40px auto 56px;
    }}

    .hero {{
      padding: 28px;
      border: 1px solid var(--border);
      border-radius: 24px;
      background: var(--surface);
      backdrop-filter: blur(10px);
      box-shadow: var(--shadow);
    }}

    h1 {{
      margin: 0 0 12px;
      font-size: clamp(2.2rem, 5vw, 3.6rem);
      line-height: 1;
      letter-spacing: -0.03em;
    }}

    .meta {{
      margin: 0;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.65;
    }}

    .controls {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 20px;
    }}

    .status,
    .empty-state {{
      margin: 16px 0 0;
      padding: 14px 16px;
      border-radius: 16px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 1rem;
      line-height: 1.65;
    }}

    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      background: var(--text);
      color: #fffdf8;
      font: inherit;
      font-size: 1rem;
      cursor: pointer;
      transition: transform 160ms ease, opacity 160ms ease;
    }}

    button.secondary {{
      background: var(--accent-soft);
      color: var(--accent);
    }}

    button:hover {{
      transform: translateY(-1px);
      opacity: 0.92;
    }}

    .chapters {{
      display: grid;
      gap: 16px;
      margin-top: 24px;
    }}

    details {{
      border: 1px solid var(--border);
      border-radius: 20px;
      background: var(--surface-strong);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    summary {{
      list-style: none;
      cursor: pointer;
      padding: 20px 24px;
      font-size: 1.15rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    summary::-webkit-details-marker {{
      display: none;
    }}

    .chapter-index {{
      flex: 0 0 auto;
      width: 2rem;
      height: 2rem;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 1rem;
    }}

    .chapter-body {{
      padding: 0 24px 24px;
      color: var(--text);
      font-size: 1.08rem;
      line-height: 1.75;
    }}

    .chapter-body p,
    .chapter-body ul {{
      margin: 0;
    }}

    .chapter-body p + p,
    .chapter-body p + ul,
    .chapter-body ul + p,
    .chapter-body ul + ul {{
      margin-top: 12px;
    }}

    .chapter-body ul {{
      padding-left: 1.25rem;
    }}

    @media (max-width: 640px) {{
      main {{
        width: min(100vw - 20px, 980px);
        margin-top: 20px;
      }}

      .hero,
      summary,
      .chapter-body {{
        padding-left: 18px;
        padding-right: 18px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>{escape(book_title)}</h1>
      <p class="meta">Source: {escape(source_file_name)}</p>
      <p class="meta">Model: {escape(model_name)}</p>
      <p class="meta">Chapters: {len(chapters)} · Generated: {escape(generated_at)}</p>
      {status_markup}
      <div class="controls">
        <button type="button" id="expand-all">Expand all</button>
        <button type="button" id="collapse-all" class="secondary">Collapse all</button>
      </div>
    </section>
    <section class="chapters">
      {empty_state}
      {chapter_sections}
    </section>
  </main>
  <script>
    const sections = document.querySelectorAll("details");
    document.getElementById("expand-all").addEventListener("click", () => {{
      sections.forEach((section) => {{
        section.open = true;
      }});
    }});
    document.getElementById("collapse-all").addEventListener("click", () => {{
      sections.forEach((section) => {{
        section.open = false;
      }});
    }});
  </script>
</body>
</html>
"""


def _render_chapter_section(*, index: int, chapter: ChapterSummary) -> str:
    return f"""<details open>
  <summary><span class="chapter-index">{index}</span>{escape(chapter.title)}</summary>
  <div class="chapter-body">{_render_summary(chapter.summary)}</div>
</details>"""


def _render_summary(summary: str) -> str:
    lines = [line.strip() for line in summary.splitlines() if line.strip()]
    if not lines:
        return "<p>The model returned an empty response.</p>"

    if all(_looks_like_list_item(line) for line in lines):
        items = "".join(
            f"<li>{escape(_strip_list_marker(line))}</li>"
            for line in lines
        )
        return f"<ul>{items}</ul>"

    paragraphs = "".join(f"<p>{escape(line)}</p>" for line in lines)
    return paragraphs


def _looks_like_list_item(line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith(("- ", "* ", "• ")):
        return True

    prefix, separator, _ = stripped.partition(". ")
    return prefix.isdigit() and bool(separator)


def _strip_list_marker(line: str) -> str:
    stripped = line.lstrip()
    for marker in ("- ", "* ", "• "):
        if stripped.startswith(marker):
            return stripped[len(marker) :].strip()

    prefix, separator, rest = stripped.partition(". ")
    if prefix.isdigit() and separator:
        return rest.strip()

    return stripped
