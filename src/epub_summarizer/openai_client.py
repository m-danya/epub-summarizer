import re
from dataclasses import dataclass

import tiktoken
from openai import AsyncOpenAI, OpenAI

from epub_summarizer.settings import Settings

FALLBACK_ENCODING = "o200k_base"
THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", flags=re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class TokenEstimate:
    count: int
    encoding_name: str
    approximate: bool


def create_client(settings: Settings) -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_api_base_url,
    )


def create_async_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_api_base_url,
    )


def resolve_model_name(client: OpenAI, configured_model_name: str | None) -> str:
    if configured_model_name:
        return configured_model_name

    models = client.models.list().data
    if not models:
        raise RuntimeError("The API returned no models from `/models`.")

    return models[0].id


def estimate_tokens(text: str, model_name: str) -> TokenEstimate:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        approximate = False
    except KeyError:
        encoding = tiktoken.get_encoding(FALLBACK_ENCODING)
        approximate = True

    return TokenEstimate(
        count=len(encoding.encode(text)),
        encoding_name=encoding.name,
        approximate=approximate,
    )


def summarize_chapter(
    client: OpenAI,
    model_name: str,
    prompt: str,
    summary_language: str,
    chapter_title: str,
    chapter_content: str,
) -> str:
    prompt_payload = build_prompt_payload(
        prompt=prompt,
        summary_language=summary_language,
        chapter_title=chapter_title,
        chapter_content=chapter_content,
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt_payload}],
    )
    return _extract_summary_content(response.choices[0].message.content, chapter_title)


async def summarize_chapter_async(
    client: AsyncOpenAI,
    model_name: str,
    prompt: str,
    summary_language: str,
    chapter_title: str,
    chapter_content: str,
) -> str:
    prompt_payload = build_prompt_payload(
        prompt=prompt,
        summary_language=summary_language,
        chapter_title=chapter_title,
        chapter_content=chapter_content,
    )

    response = await client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt_payload}],
    )
    return _extract_summary_content(response.choices[0].message.content, chapter_title)


def build_prompt_payload(
    *,
    prompt: str,
    summary_language: str,
    chapter_title: str,
    chapter_content: str,
) -> str:
    return (
        f"{prompt.strip()}\n\n"
        f"Summary language: {summary_language}\n"
        "Return the summary in that language.\n\n"
        f"Chapter title: {chapter_title}\n\n"
        f"Chapter text:\n{chapter_content.strip()}"
    )


def strip_model_thinking(content: str) -> str:
    return THINK_BLOCK_RE.sub("", content).strip()


def _extract_summary_content(content: str | None, chapter_title: str) -> str:
    if not content:
        raise RuntimeError(f"Empty model response for chapter: {chapter_title}")

    cleaned_content = strip_model_thinking(content)
    if not cleaned_content:
        raise RuntimeError(
            "The model response became empty after filtering `<think>` blocks "
            f"for chapter: {chapter_title}"
        )

    return cleaned_content
