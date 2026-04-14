from __future__ import annotations

import argparse
import asyncio
import re
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from epub_summarizer.epub_parser import extract_chapters
from epub_summarizer.html_report import render_report
from epub_summarizer.models import Chapter, ChapterSummary
from epub_summarizer.openai_client import (
    build_prompt_payload,
    create_async_client,
    create_client,
    estimate_tokens,
    resolve_model_name,
    summarize_chapter_async,
)
from epub_summarizer.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="epub-summarizer",
        description="Generate an HTML summary report for an EPUB file.",
    )
    parser.add_argument("epub_file", type=Path, help="Path to the .epub file")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--limit",
        type=_positive_int,
        help="Summarize only the first N chapters.",
    )
    mode_group.add_argument(
        "--extract-chapter",
        type=_positive_int,
        help="Save the text of the 1-based N-th extracted chapter to a `.txt` file.",
    )
    parser.add_argument(
        "--summary-language",
        default="ru",
        type=_non_empty_string,
        help="Language for the generated summary, for example: ru, en, de.",
    )
    parser.add_argument(
        "--parallel-requests-num",
        default=4,
        type=_positive_int,
        help="Maximum number of concurrent LLM requests.",
    )
    args = parser.parse_args()
    run(
        args.epub_file,
        extract_chapter=args.extract_chapter,
        limit=args.limit,
        parallel_requests_num=args.parallel_requests_num,
        summary_language=args.summary_language,
    )


def run(
    epub_file: Path,
    *,
    extract_chapter: int | None = None,
    limit: int | None = None,
    parallel_requests_num: int = 4,
    summary_language: str = "ru",
) -> Path:
    epub_file = epub_file.expanduser().resolve()
    if not epub_file.is_file():
        raise SystemExit(f"File not found: {epub_file}")

    if epub_file.suffix.lower() != ".epub":
        raise SystemExit(f"Expected a `.epub` file, got: {epub_file.name}")

    chapters = extract_chapters(epub_file)
    total_chapters_in_book = len(chapters)
    if extract_chapter is not None:
        return _extract_chapter_to_file(
            chapters=chapters,
            chapter_number=extract_chapter,
        )

    try:
        settings = Settings()
    except ValidationError as error:
        raise SystemExit(f"Failed to load settings from `.env`: {error}") from error

    prompt = _load_prompt()

    if limit is not None:
        chapters = chapters[:limit]
        if not chapters:
            raise SystemExit("No chapters remain after applying `--limit`.")

    client = create_client(settings)
    try:
        model_name = resolve_model_name(client, settings.openai_model_name)
    finally:
        client.close()

    output_path = Path.cwd() / _build_report_file_name(
        book_stem=epub_file.stem,
        model_name=model_name,
    )
    largest_chapter = max(chapters, key=lambda chapter: len(chapter.content))
    largest_chapter_estimate = estimate_tokens(largest_chapter.content, model_name)
    largest_prompt_estimate = estimate_tokens(
        build_prompt_payload(
            prompt=prompt,
            summary_language=summary_language,
            chapter_title=largest_chapter.title,
            chapter_content=largest_chapter.content,
        ),
        model_name,
    )
    summarized_by_index: dict[int, ChapterSummary] = {}
    summarized_chapters: list[ChapterSummary] = []
    interrupt_message: str | None = None

    print(f"Selected model: {model_name}")
    print(f"Summary language: {summary_language}")
    print(f"Parallel requests: {parallel_requests_num}")
    print(f"Chapters found in book: {total_chapters_in_book}")
    if limit is not None:
        print(f"Processing the first {len(chapters)} chapters.")
    else:
        print(f"Processing all chapters: {len(chapters)}")
    print(
        f'Largest chapter: "{largest_chapter.title}". '
        "Chapter size: "
        f"{len(largest_chapter.content)} characters, "
        f"~{largest_chapter_estimate.count} tokens."
    )
    print(
        "Estimated full prompt size for that chapter: "
        f"~{largest_prompt_estimate.count} tokens."
    )
    if largest_prompt_estimate.approximate:
        print(
            "The model is not recognized by `tiktoken`, so the approximate "
            f"`{largest_prompt_estimate.encoding_name}` encoding was used."
        )

    try:
        input("Press Enter to continue, or Ctrl+C to cancel...")
        asyncio.run(
            _summarize_chapters(
                settings=settings,
                chapters=chapters,
                model_name=model_name,
                prompt=prompt,
                summary_language=summary_language,
                parallel_requests_num=parallel_requests_num,
                summarized_by_index=summarized_by_index,
            )
        )
        summarized_chapters = [
            summarized_by_index[index] for index in sorted(summarized_by_index)
        ]
    except KeyboardInterrupt:
        summarized_chapters = [
            summarized_by_index[index] for index in sorted(summarized_by_index)
        ]
        interrupt_message = (
            "The run was interrupted. "
            f"Saved {len(summarized_chapters)} of {len(chapters)} chapter summaries."
        )
        print("\nInterrupted by user. Saving the available results...")

    output_path.write_text(
        render_report(
            book_title=epub_file.stem,
            source_file_name=epub_file.name,
            model_name=model_name,
            chapters=summarized_chapters,
            status_message=interrupt_message,
        ),
        encoding="utf-8",
    )
    print(f"HTML report saved: {output_path}")

    if interrupt_message is not None:
        raise SystemExit(130)

    return output_path


def _extract_chapter_to_file(*, chapters: list[Chapter], chapter_number: int) -> Path:
    if chapter_number > len(chapters):
        raise SystemExit(
            "Chapter index out of range: "
            f"{chapter_number}. Available chapters: 1-{len(chapters)}."
        )

    chapter = chapters[chapter_number - 1]
    output_path = Path.cwd() / f"extracted_chapter_{uuid4()}_{chapter_number}.txt"
    output_path.write_text(chapter.content, encoding="utf-8")
    print(f"Extracted chapter [{chapter_number}/{len(chapters)}]: {chapter.title}")
    print(f"Chapter text saved: {output_path}")
    return output_path


def _build_report_file_name(*, book_stem: str, model_name: str) -> str:
    normalized_model_name = _normalize_for_file_name(model_name)
    return f"{book_stem}_{normalized_model_name}_{uuid4()}.html"


def _normalize_for_file_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("._-")
    return normalized or "model"


def _load_prompt() -> str:
    return (
        files("epub_summarizer.prompts")
        .joinpath("chapter_summary.txt")
        .read_text(encoding="utf-8")
    )


async def _summarize_chapters(
    *,
    settings: Settings,
    chapters: list[Chapter],
    model_name: str,
    prompt: str,
    summary_language: str,
    parallel_requests_num: int,
    summarized_by_index: dict[int, ChapterSummary],
) -> None:
    semaphore = asyncio.Semaphore(parallel_requests_num)
    total_chapters = len(chapters)

    async with create_async_client(settings) as client:

        async def summarize(index: int, chapter: Chapter) -> None:
            async with semaphore:
                print(f"[{index}/{total_chapters}] Summarizing: {chapter.title}")
                summary = await summarize_chapter_async(
                    client=client,
                    model_name=model_name,
                    prompt=prompt,
                    summary_language=summary_language,
                    chapter_title=chapter.title,
                    chapter_content=chapter.content,
                )
                summarized_by_index[index] = ChapterSummary(
                    title=chapter.title,
                    summary=summary,
                )

        tasks = [
            asyncio.create_task(summarize(index, chapter))
            for index, chapter in enumerate(chapters, start=1)
        ]
        try:
            for task in asyncio.as_completed(tasks):
                await task
        finally:
            pending_tasks = [task for task in tasks if not task.done()]
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("The value must be an integer.") from error

    if parsed <= 0:
        raise argparse.ArgumentTypeError("The value must be greater than zero.")

    return parsed


def _non_empty_string(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("The value must not be empty.")

    return normalized
