# epub-summarizer

A CLI tool that reads an `.epub`, sends each chapter to an LLM, and builds a single HTML report with concise chapter summaries based on the book's table of contents.

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
