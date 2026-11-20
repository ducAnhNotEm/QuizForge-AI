"""Tests for prompt-to-provider orchestration without a live LLM."""

import asyncio

from backend.generation import generate_questions
from backend.llm_client import LLMResponse
from backend.schemas import RetrievedChunk


class FakeLLMClient:
    def __init__(self):
        self.payload = None

    async def generate(self, payload):
        self.payload = payload
        return LLMResponse(
            content='{"questions": [], "refusal_reason": "context too short"}',
            provider="fake",
            model="fake-model",
            prompt_tokens=12,
            completion_tokens=4,
            finish_reason="stop",
        )


def test_generate_questions_builds_prompt_and_keeps_source_handoff():
    async def scenario():
        llm_client = FakeLLMClient()
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            doc_id="doc-1",
            course_id="course-1",
            file_name="lesson.txt",
            page=2,
            chunk_index=0,
            content="Tìm kiếm nhị phân áp dụng cho mảng đã sắp xếp.",
            score=0.9,
        )

        result = await generate_questions(
            [chunk],
            course_name="Cấu trúc dữ liệu",
            bloom_level="understand",
            difficulty="easy",
            llm_client=llm_client,
        )

        assert llm_client.payload is not None
        assert llm_client.payload.messages[0]["role"] == "system"
        assert "Cấu trúc dữ liệu" in llm_client.payload.messages[1]["content"]
        assert result.raw_output.startswith('{"questions"')
        assert result.provider == "fake"
        assert result.prompt_version == llm_client.payload.prompt_version
        assert result.source_refs == llm_client.payload.source_refs
        assert result.source_refs[0].page == 2
        assert result.prompt_tokens == 12

    asyncio.run(scenario())
