import hashlib
import json
from sqlalchemy.orm import Session
from app.models import Document, DocumentContent, Run, RunStep, Citation
from app.audit.service import append_event
from app.pipeline.tokens import choose_strategy
from app.pipeline.summarize import run_map_reduce
from app.pipeline.citations import verify_quote
from app.pipeline.prompts import SUMMARIZE_SYSTEM_PROMPT
from app.llm.openai_compat import make_groq_provider

from app.llm.mock import MockProvider
from app.pipeline.circuit_breaker import should_use_mock


async def execute_run(session: Session, *, document: Document, actor_id: int, actor_role: str) -> Run:
    content = session.get(DocumentContent, document.id)
    input_sha256 = hashlib.sha256(content.text.encode("utf-8")).hexdigest()

    use_mock = should_use_mock(session)
    run = Run(
        document_id=document.id, requested_by=actor_id,
        provider="mock" if use_mock else "groq",
        model="mock-model" if use_mock else "openai/gpt-oss-120b",
        strategy="pending",
        input_sha256=input_sha256, status="running",
    )
    
    session.add(run)
    session.flush()

    append_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="run.created", entity_type="run", entity_id=run.id,
        payload={"document_id": document.id, "provider": run.provider, "model": run.model},
    )
    session.commit()


    if use_mock:
        provider = MockProvider()
        append_event(
            session, actor_id=actor_id, actor_role=actor_role,
            action="run.circuit_breaker_triggered", entity_type="run", entity_id=run.id,
            payload={"reason": "daily_token_cap_reached"},
        )
    else:
        provider = make_groq_provider()    
    
    strategy = choose_strategy(content.text)
    run.strategy = strategy
    session.commit()

    if strategy == "single":
        result = await provider.complete(system=SUMMARIZE_SYSTEM_PROMPT, user=content.text)
        parsed = json.loads(result.text)
        session.add(RunStep(
            run_id=run.id, step_index=1, kind="single", input_sha256=input_sha256,
            output_text=result.text, prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens, latency_ms=result.latency_ms,
        ))
        total_prompt_tokens = result.prompt_tokens
        total_completion_tokens = result.completion_tokens
    else:
        parsed, step_records = await run_map_reduce(provider, content.text)
        total_prompt_tokens = 0
        total_completion_tokens = 0
        for step in step_records:
            step_text = content.text[step["chunk_start"]:step["chunk_end"]] if step["chunk_start"] is not None else content.text
            step_hash = hashlib.sha256(step_text.encode("utf-8")).hexdigest()
            session.add(RunStep(
                run_id=run.id, step_index=step["step_index"], kind=step["kind"],
                input_sha256=step_hash, output_text=step["output_text"],
                prompt_tokens=step["prompt_tokens"], completion_tokens=step["completion_tokens"],
                latency_ms=step["latency_ms"],
            ))
            total_prompt_tokens += step["prompt_tokens"]
            total_completion_tokens += step["completion_tokens"]

    key_points_with_verification = []
    for kp in parsed.get("key_points", []):
        verified, char_start, char_end = verify_quote(content.text, kp["quote"])
        session.add(Citation(
            run_id=run.id, key_point=kp["point"], quote=kp["quote"],
            verified=verified, char_start=char_start, char_end=char_end,
        ))
        key_points_with_verification.append((kp, verified))

    verified_count = sum(1 for _, v in key_points_with_verification if v)
    total_count = len(key_points_with_verification)

    run.status = "succeeded"
    run.result_json = json.dumps(parsed)
    run.total_prompt_tokens = total_prompt_tokens
    run.total_completion_tokens = total_completion_tokens

    append_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="run.completed", entity_type="run", entity_id=run.id,
        payload={
            "status": "succeeded", "strategy": strategy,
            "prompt_tokens": total_prompt_tokens, "completion_tokens": total_completion_tokens,
            "citations_verified": verified_count, "citations_total": total_count,
        },
    )
    session.commit()

    run.parsed_result = parsed
    run.key_points_with_verification = key_points_with_verification
    run.verified_count = verified_count
    run.total_count = total_count

    return run