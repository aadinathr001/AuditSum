import time
import os
from openai import AsyncOpenAI
from app.llm.base import LLMResult

from tenacity import retry, stop_after_attempt, wait_exponential_jitter
from openai import RateLimitError

class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.name = f"openai_compat:{model}"
        self.model = model
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        
    @retry(
        retry=lambda retry_state: isinstance(
            retry_state.outcome.exception(),
            RateLimitError,
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
    )
    
    async def complete(self, *, system: str, user: str) -> LLMResult:
        start = time.monotonic()

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]

        return LLMResult(
            text=choice.message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            latency_ms=latency_ms,
            model=self.model,
        )


def make_groq_provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
        model="openai/gpt-oss-120b",
    )