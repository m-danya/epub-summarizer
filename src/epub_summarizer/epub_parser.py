from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from epub_summarizer.models import Chapter

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass(frozen=True)
class TocEntry:
    title: str
    href: str
    path: str
    anchor: str | None


def extract_chapters(epub_path: Path) -> list[Chapter]:
    book = epub.read_epub(str(epub_path))
    toc_entries = _flatten_toc(book.toc) or _chapters_from_spine(book)
    if not toc_entries:
        raise RuntimeError("Could not find chapters in either the table of contents or the spine.")

    documents = {
        _normalize_path(item.file_name): item
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
    }

    chapters_by_index: dict[int, Chapter] = {}
    entries_by_path: dict[str, list[tuple[int, TocEntry]]] = defaultdict(list)
    for index, entry in enumerate(toc_entries):
        entries_by_path[entry.path].append((index, entry))

    for path, indexed_entries in entries_by_path.items():
        item = documents.get(path)
        if item is None:
            continue

        html = item.get_content().decode("utf-8", errors="ignore")
        extracted_texts = _extract_document_sections(
            html=html,
            entries=[entry for _, entry in indexed_entries],
        )

        for (index, entry), text in zip(indexed_entries, extracted_texts):
            cleaned_text = _clean_text(text)
            if cleaned_text:
                chapters_by_index[index] = Chapter(title=entry.title, content=cleaned_text)

    chapters = [chapters_by_index[index] for index in sorted(chapters_by_index)]
    if not chapters:
        raise RuntimeError("Could not extract chapter text from the EPUB.")

    return chapters


def _flatten_toc(toc: object) -> list[TocEntry]:
    entries: list[TocEntry] = []

    def walk(node: object) -> None:
        if isinstance(node, (list, tuple)):
            if len(node) == 2 and isinstance(node[1], (list, tuple)):
                walk(node[0])
                walk(node[1])
                return

            for child in node:
                walk(child)
            return

        entry = _toc_item_to_entry(node)
        if entry is not None:
            entries.append(entry)

    walk(toc)
    return entries


def _chapters_from_spine(book: epub.EpubBook) -> list[TocEntry]:
    documents = {item.get_id(): item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)}
    entries: list[TocEntry] = []

    for spine_item in book.spine:
        item_id = spine_item[0] if isinstance(spine_item, tuple) else spine_item
        document = documents.get(item_id)
        if document is None:
            continue

        path = _normalize_path(document.file_name)
        title = document.title or Path(path).stem
        entries.append(
            TocEntry(
                title=title,
                href=document.file_name,
                path=path,
                anchor=None,
            )
        )

    return entries


def _toc_item_to_entry(item: object) -> TocEntry | None:
    href = getattr(item, "href", None) or getattr(item, "file_name", None)
    if not href:
        return None

    title = getattr(item, "title", None)
    if not title and hasattr(item, "get_name"):
        title = item.get_name()

    path, anchor = _split_href(href)
    if not path:
        return None

    normalized_title = _clean_title(title) or Path(path).stem
    return TocEntry(title=normalized_title, href=href, path=path, anchor=anchor)


def _split_href(href: str) -> tuple[str, str | None]:
    clean_href = unquote(href.split("?", maxsplit=1)[0])
    path, _, anchor = clean_href.partition("#")
    return _normalize_path(path), anchor or None


def _normalize_path(path: str) -> str:
    normalized = path.strip().lstrip("./")
    return normalized


def _extract_document_sections(html: str, entries: list[TocEntry]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    body = soup.body or soup
    full_text = _clean_text(body.get_text("\n"))
    if not full_text:
        return [""] * len(entries)

    if len(entries) == 1:
        return [full_text]

    markers: list[str] = []
    inserted_indexes: set[int] = set()
    for index, entry in enumerate(entries):
        marker = f"[[[EPUB_SUMMARY_MARKER_{index}]]]"
        markers.append(marker)
        target = _find_section_target(body, entry)

        if target is None:
            if index == 0:
                body.insert(0, soup.new_string(f"\n{marker}\n"))
                inserted_indexes.add(index)
            continue

        target.insert_before(soup.new_string(f"\n{marker}\n"))
        inserted_indexes.add(index)

    if not inserted_indexes:
        return [full_text for _ in entries]

    end_marker = "[[[EPUB_SUMMARY_END]]]"
    body.append(soup.new_string(f"\n{end_marker}\n"))
    marked_text = body.get_text("\n")
    end_position = marked_text.find(end_marker)

    positions = []
    for index, marker in enumerate(markers):
        position = marked_text.find(marker)
        if position != -1:
            positions.append((index, position, len(marker)))

    sections = [""] * len(entries)
    for current_index, (entry_index, start_position, marker_length) in enumerate(positions):
        next_position = (
            positions[current_index + 1][1]
            if current_index + 1 < len(positions)
            else end_position
        )
        sections[entry_index] = _clean_text(
            marked_text[start_position + marker_length : next_position]
        )

    for index, section in enumerate(sections):
        if not section:
            sections[index] = full_text

    return sections


def _find_section_target(body: BeautifulSoup, entry: TocEntry):
    if entry.anchor:
        target = body.find(id=entry.anchor) or body.find(attrs={"name": entry.anchor})
        if target is not None:
            return target

    normalized_title = _normalize_text_for_match(entry.title)
    if not normalized_title:
        return None

    for heading in body.find_all(HEADING_TAGS):
        heading_text = _normalize_text_for_match(heading.get_text(" ", strip=True))
        if heading_text == normalized_title or normalized_title in heading_text:
            return heading

    return None


def _clean_title(title: str | None) -> str:
    if title is None:
        return ""

    return re.sub(r"\s+", " ", str(title)).strip()


def _normalize_text_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _clean_text(text: str) -> str:
    normalized = text.replace("\xa0", " ")
    normalized = re.sub(r"\r", "", normalized)
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    lines = [line.strip() for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line).strip()
