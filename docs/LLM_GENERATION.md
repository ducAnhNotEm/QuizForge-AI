# LLM generation configuration

The M3 generation module uses async HTTP requests through the already-installed
`httpx` dependency. It supports Gemini, OpenAI, and a local Ollama server. The
provider calls use the official Gemini `generateContent`, OpenAI Chat
Completions, and Ollama `/api/chat` interfaces.

## Environment variables

```dotenv
QUIZFORGE_LLM_PROVIDER=ollama
QUIZFORGE_LLM_MODEL=<model-name-installed-in-ollama>
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

For Gemini, set `QUIZFORGE_LLM_PROVIDER=gemini`, `QUIZFORGE_LLM_MODEL`, and
`GEMINI_API_KEY`. For OpenAI, set `QUIZFORGE_LLM_PROVIDER=openai`,
`QUIZFORGE_LLM_MODEL`, and `OPENAI_API_KEY`.

Optional settings:

| Variable | Default | Purpose |
|---|---:|---|
| `QUIZFORGE_LLM_TIMEOUT_SECONDS` | `45` | Per-request timeout |
| `QUIZFORGE_LLM_MAX_RETRIES` | `3` | Retries after network, timeout, rate-limit, and server errors |
| `QUIZFORGE_LLM_BACKOFF_BASE_SECONDS` | `0.5` | First exponential-backoff delay |
| `QUIZFORGE_LLM_BACKOFF_MAX_SECONDS` | `8` | Cap for locally calculated delays |
| `QUIZFORGE_LLM_TEMPERATURE` | `0.2` | Generation temperature |
| `QUIZFORGE_LLM_TOP_P` | `0.9` | Nucleus sampling setting |
| `QUIZFORGE_LLM_MAX_OUTPUT_TOKENS` | `2048` | Output token limit |
| `QUIZFORGE_LLM_MAX_INPUT_TOKENS` | `12000` | Estimated prompt token ceiling |

Provider-specific base URLs can be overridden with `GEMINI_API_BASE_URL`,
`OPENAI_API_BASE_URL`, and `OLLAMA_BASE_URL`.

The prompt-size check uses the project's conservative character-based token
estimate. It is a guardrail, not a substitute for each model's tokenizer. The
generation function returns raw model output and source metadata; SV3's quality
gate remains responsible for parsing and validating the question JSON.

## Python usage

```python
from backend.generation import generate_questions
from backend.llm_client import LLMClient

async with LLMClient.from_env() as llm:
    result = await generate_questions(
        retrieved_chunks,
        course_name="Cấu trúc dữ liệu",
        bloom_level="understand",
        difficulty="medium",
        count=3,
        llm_client=llm,
    )
    # Pass result.raw_output and result.source_refs to the quality gate.
```
