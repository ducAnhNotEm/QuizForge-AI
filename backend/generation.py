"""Question-generation orchestration for M3.

This module builds the existing SV1 prompt and sends it to the SV2 LLM client.
It returns raw model output plus source metadata; JSON parsing and target-schema
validation remain with the SV3 quality-gate module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Union

from backend.exam_context import AssembledContext, ContextSource, DEFAULT_MAX_CONTEXT_TOKENS
from backend.llm_client import LLMClient, LLMResponse
from backend.prompts import PromptPayload, build_mcq_prompt
from backend.schemas import BloomLevel, DifficultyLevel, RetrievedChunk


@dataclass(frozen=True)
class GenerationResult:
    raw_output: str
    provider: str
    model: str
    prompt_version: str
    response_schema: dict
    source_refs: tuple[ContextSource, ...]
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None


async def generate_from_prompt(
    prompt: PromptPayload,
    *,
    llm_client: LLMClient,
) -> GenerationResult:
    """Send a prepared prompt to the provider without parsing its response."""

    response: LLMResponse = await llm_client.generate(prompt)
    return GenerationResult(
        raw_output=response.content,
        provider=response.provider,
        model=response.model,
        prompt_version=prompt.prompt_version,
        response_schema=prompt.response_schema,
        source_refs=prompt.source_refs,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        finish_reason=response.finish_reason,
    )


async def generate_questions(
    context: Union[AssembledContext, Sequence[RetrievedChunk]],
    *,
    course_name: str,
    bloom_level: Union[BloomLevel, str],
    difficulty: Union[DifficultyLevel, str],
    llm_client: LLMClient,
    count: int = 1,
    concept: Optional[str] = None,
    misconceptions: Optional[Sequence[str]] = None,
    language: str = "vi",
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
) -> GenerationResult:
    """Build an M3 prompt from retrieved context and generate raw model output."""

    prompt = build_mcq_prompt(
        context,
        course_name=course_name,
        bloom_level=bloom_level,
        difficulty=difficulty,
        count=count,
        concept=concept,
        misconceptions=misconceptions,
        language=language,
        max_context_tokens=max_context_tokens,
    )
    return await generate_from_prompt(prompt, llm_client=llm_client)
