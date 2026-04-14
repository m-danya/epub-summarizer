# epub-summarizer

A CLI tool that reads an `.epub`, sends each chapter to an LLM, and builds a single HTML report with concise chapter summaries based on the book's table of contents.

## Demo

You can check out the demo [here](https://m-danya.github.io/epub-summarizer/).
This HTML was generated with the following command:

```bash
m-danya ~/code/epub-summarizer$ uv run epub-summarizer "Тьюринг А._Может ли машина мыслить.epub" --limit 10
Selected model: qwen3.5-9b-uncensored-hauhaucs-aggressive@q4_k_m
Summary language: ru
Parallel requests: 4
Chapters found in book: 19
Processing the first 10 chapters.
Largest chapter: "IV. Цифровые вычислительные машины". Chapter size: 9105 characters, ~2220 tokens.
Estimated full prompt size for that chapter: ~2295 tokens.
The model is not recognized by `tiktoken`, so the approximate `o200k_base` encoding was used.
Press Enter to continue, or Ctrl+C to cancel...
[1/10] Summarizing: Алан Тьюринг Могут ли машины мыслить?
[2/10] Summarizing: I. Игра в имитацию
[3/10] Summarizing: II. Критика новой постановки проблемы
[4/10] Summarizing: III. Машины, привлекаемые к игре
[5/10] Summarizing: IV. Цифровые вычислительные машины
[6/10] Summarizing: V. Универсальность цифровых вычислительных машин
[7/10] Summarizing: VI. Противоположные точки зрения по основному вопросу
[8/10] Summarizing: 1. Теологическое возражение
[9/10] Summarizing: 2. Возражение со «страусиной» точки зрения
[10/10] Summarizing: 3. Математическое возражение
HTML report saved: /home/m-danya/code/epub-summarizer/Тьюринг А._Может ли машина мыслить_qwen3.5-9b-uncensored-hauhaucs-aggressive_q4_k_m_123e4567-e89b-12d3-a456-426614174000.html
```

### Vibecoding notice

This project is vibecoded without any code review.

## `.env` Setup

The tool reads configuration from `.env` in the current directory via `pydantic-settings`.

Example:

```dotenv
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your_api_key
OPENAI_MODEL_NAME=
```


You can use local models, as long as they expose an OpenAI-compatible API. For
example, this works with tools like LM Studio or vLLM by pointing
OPENAI_API_BASE_URL to the local server.

`OPENAI_MODEL_NAME` and `OPENAI_API_KEY` are optional. If `OPENAI_MODEL_NAME` is
not set, the program queries `/models` and uses the first available model.

## Usage

```bash
uv run epub-summarizer path/to/book.epub
```

HTML reports are saved as `./{book_stem}_{normalized_model_name}_{uuid}.html`.

To extract the plain text of the N-th extracted chapter (without calling the LLM):

```bash
uv run epub-summarizer path/to/book.epub --extract-chapter 5
```

This saves the chapter text to `./extracted_chapter_{uuid}_5.txt` and prints the
full path to the saved file.

To explicitly set the summary language:

```bash
uv run epub-summarizer path/to/book.epub --summary-language ru
```

For a test run on only the first chapters:

```bash
uv run epub-summarizer path/to/book.epub --limit 3 --summary-language ru
```

To control how many chapter requests are sent to the LLM in parallel:

```bash
uv run epub-summarizer path/to/book.epub --parallel-requests-num 8
```

By default, the CLI sends up to 4 chapter requests in parallel. If the model returns
an internal reasoning block in `<think>...</think>`, it is stripped before the summary
is saved to the HTML report.

What the command does:

1. Reads the EPUB and extracts chapters from the table of contents.
2. Finds the largest chapter and shows its approximate token size for the selected model.
3. Waits for confirmation via Enter.
4. Asks the LLM for a short summary of each chapter in the requested language, using
   up to 4 parallel requests by default.
5. Saves a **single HTML file with collapsible sections for each chapter**.
