import re
import json
from app.llm.base import LLMResult


class MockProvider:
    name = "mock"

    def __init__(self, hallucinate: bool = False):
        self.hallucinate = hallucinate

    async def complete(self, *, system: str, user: str) -> LLMResult:
        if self.hallucinate:
            quote = "this exact phrase does not appear anywhere in the source"
        else:
            first_sentence_match = re.search(r"[^.!?]+[.!?]", user)
            quote = first_sentence_match.group(0).strip() if first_sentence_match else user[:50]

        response = { "title": "Mock Summary", 
                    "summary": "This is a deterministic mock summary for testing.", 
                    "key_points": [ { "point": "First key idea", "quote": quote, } ], 
                    "action_items": ["Review the mock output"], } 
        fake_summary = json.dumps(response)

        return LLMResult(
            text=fake_summary,
            prompt_tokens=len(user) // 4,
            completion_tokens=len(fake_summary) // 4,
            latency_ms=50,
            model="mock-model",
        )