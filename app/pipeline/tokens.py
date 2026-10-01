import os
from dotenv import load_dotenv
load_dotenv()

SINGLE_CALL_LIMIT = int(os.getenv("SINGLE_CALL_LIMIT", "5000"))


def estimate_tokens(text: str) -> int:
    return len(text) // 4

def choose_strategy(text: str) -> str:
    if estimate_tokens(text) <= SINGLE_CALL_LIMIT:
        return "single"
    return "map_reduce"

