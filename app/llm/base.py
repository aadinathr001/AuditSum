from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model: str


class LLMProvider(Protocol):
    name: str

    async def complete(self, *, system: str, user: str) -> LLMResult:
        ...