import json
from app.pipeline.chunker import chunk_text
from app.pipeline.prompts import MAP_SYSTEM_PROMPT, REDUCE_SYSTEM_PROMPT


async def run_map_reduce(provider, text: str) -> tuple[dict, list[dict]]:
    chunks = chunk_text(text)
    step_records = []

    all_key_points = []

    for i, chunk in enumerate(chunks):
        result = await provider.complete(system=MAP_SYSTEM_PROMPT, user=chunk.text)
        parsed = json.loads(result.text)

        step_records.append({
            "step_index": i + 1,
            "kind": "map",
            "chunk_start": chunk.char_start,
            "chunk_end": chunk.char_end,
            "output_text": result.text,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "latency_ms": result.latency_ms,
        })

        all_key_points.extend(parsed.get("key_points", []))

    reduce_input = json.dumps({"key_points": all_key_points})
    reduce_result = await provider.complete(system=REDUCE_SYSTEM_PROMPT, user=reduce_input)
    final_parsed = json.loads(reduce_result.text)

    step_records.append({
        "step_index": len(chunks) + 1,
        "kind": "reduce",
        "chunk_start": None,
        "chunk_end": None,
        "output_text": reduce_result.text,
        "prompt_tokens": reduce_result.prompt_tokens,
        "completion_tokens": reduce_result.completion_tokens,
        "latency_ms": reduce_result.latency_ms,
    })

    return final_parsed, step_records